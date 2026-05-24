# LSTM 滚动窗口标准化设计

## 问题

当前 LSTM 使用 per-window Z-score 标准化（每个60天序列独立做 mean/std），导致趋势信息完全丢失。上涨趋势和下跌趋势的序列标准化后数据分布相同，模型无法区分方向。

## 目标

1. 用 T 日之前的滚动窗口统计量（mean/std）标准化训练数据，保留趋势方向
2. 预测时使用训练时保存的统计量，确保训练/预测一致
3. 添加 close、vol 特征

## 当前代码链路

训练：`classifier.py:train()` → `normalizer.py:create_sequences()` → per-window Z-score
预测：`classifier.py:predict_proba()` → 对输入序列自己做 per-window Z-score

## 改动设计

### 1. normalizer.py — 新增 `create_sequences_rolling`

```python
def create_sequences_rolling(
    df: pd.DataFrame,
    feature_fields: List[str],
    target_names: List[str],
    sequence_length: int,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Tuple[np.ndarray, np.ndarray]]]:
    """
    滚动窗口标准化创建训练序列。
    
    对每只股票：
    1. 按日期排序
    2. 对每个 T 日的序列，用 [lookback_start, T-1] 的滚动窗口计算 mean/std
    3. 用该 mean/std 标准化 T 日的序列
    
    返回：
    - X_3d: 标准化后的序列
    - y_2d: 标签
    - norm_params: {ts_code: (means, stds)}，保存的最新统计量，用于预测
    """
```

**统计量计算规则**：
- 对每只股票，取 `[T - lookback_days, T-1]` 的数据计算 mean/std
- `lookback_days = sequence_length * 2`（至少120天，确保统计稳定）
- 如果历史数据不足 lookback_days，则使用所有可用数据

**norm_params 结构**：
```python
{
    "000001.SZ": {
        "means": np.ndarray,  # shape: (n_features,)
        "stds": np.ndarray,   # shape: (n_features,)
    }
}
```

### 2. classifier.py — 保存 norm_params

**train 方法**：
- 调用 `create_sequences_rolling` 替代 `create_sequences`
- 将返回的 `norm_params` 保存到 `self._norm_params`
- 清理非价格特征的 mean/std 不必要，所有特征都使用 rolling normalizer

**save 方法**：
```python
torch.save({
    "models": {...},
    "label_mapping": self._label_mapping,
    "input_size": self.input_size,
    "sequence_length": self.sequence_length,
    "norm_params": self._norm_params,  # 新增
}, path)
```

**load 方法**：
```python
self._norm_params = state.get("norm_params", {})  # 兼容旧模型
```

**predict/predict_proba 方法**：
- 新增 `ts_code` 参数（默认为 None）
- 如果有 `ts_code` 且 `self._norm_params` 中包含该股票，则使用保存的统计量
- 否则回退到 per-window 标准化

```python
def predict_proba(self, features, target_names, ts_code=None):
    seq = np.array(features, dtype=np.float64)
    if len(seq) < self.sequence_length:
        return {t: [0.0, 0.0, 0.0] for t in target_names}
    seq = seq[-self.sequence_length:]
    
    if ts_code and ts_code in self._norm_params:
        # 使用训练时保存的统计量
        norm = self._norm_params[ts_code]
        seq = (seq - norm["means"]) / norm["stds"]
        seq = np.nan_to_num(seq, nan=0.0, posinf=0.0, neginf=0.0)
    else:
        # 回退到 per-window 标准化
        seq_mean, seq_std = seq.mean(axis=0), seq.std(axis=0)
        seq_std[seq_std == 0] = 1.0
        seq = np.nan_to_num((seq - seq_mean) / seq_std, nan=0.0)
    
    X_tensor = torch.FloatTensor(seq).unsqueeze(0)
    ...
```

### 3. predictor.py — 传递 ts_code

**predict_batch_with_history**：
```python
for ts_code in ts_codes:
    stock = df[df["ts_code"] == ts_code].sort_values("trade_date")
    if len(stock) < seq_len:
        continue
    features = stock[self._config.feature_fields].values[-seq_len:]
    if np.isnan(features).any():
        continue
    self._predict_and_add(result, ts_code, day_df, features, target_names)
```

predict/predict_proba 调用时不需要额外参数——在 `_predict_and_add` 中 ts_code 已经可用，但当前 `_classifier.predict()` 和 `_classifier.predict_proba()` 接口不接受 ts_code。

**要在 classifier 的 predict/predict_proba 中传递 ts_code，需要在调用处传入**：

`_predict_and_add` 方法需要修改调用，但这会改变 LSTMClassifier 的公共接口。有两种方案：

**方案A（推荐）**：在 LSTMClassifier 实例化时设置 ts_code，然后每次传入 features

实际上最简单的方式是在 `_predict_and_add` 中对 LSTM 单独处理 ts_code：

```python
def _predict_and_add(self, result, ts_code, day_df, features, target_names):
    if self._config.model_type == "lstm":
        predictions = self._classifier.predict(features, target_names, ts_code=ts_code)
        probabilities = self._classifier.predict_proba(features, target_names, ts_code=ts_code)
    else:
        predictions = self._classifier.predict(features, target_names)
        probabilities = self._classifier.predict_proba(features, target_names)
    ...
```

### 4. config.py — 添加 close/vol 特征

在 `DEFAULT_INDICATOR_FIELDS` 开头添加：

```python
DEFAULT_INDICATOR_FIELDS = [
    "close", "vol",  # 新增
    "ma_5", "ma_10", ...
]
```

### 5. 兼容性

- 旧模型文件不包含 `norm_params`，`load` 方法中 `get("norm_params", {})` 确保不报错
- 回退到 per-window 标准化，行为不变

## 测试

- 单元测试：验证 rolling normalizer 输出非零序列
- 单元测试：验证相同的 norm_params 用于训练和预测
- 单元测试：验证旧模型加载兼容性
