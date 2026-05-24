# LSTM 标准化窗口分离设计

## 背景

当前 LSTM `create_sequences` 在每个 `sequence_length`（默认 60）天的窗口内独立做 Z-score 归一化。每个窗口用自身 60 天的 mean/std 归一化，丢失了跨窗口的趋势和相对位置信息。

## 目标

将标准化窗口从序列长度中分离出来：标准化统计量基于更大的窗口（默认 300 天）计算，但只对最后 `sequence_length` 天的数据做归一化，输出 60 天的序列。模型保持接收 60 维时序输入，但价格在大背景下的相对位置被保留。

## 改动汇总

| 文件 | 改动 |
|------|------|
| `models/training/config.py` | 新增 `lstm_normalization_window` 参数，默认 300 |
| `models/lstm/normalizer.py` | `create_sequences` 新增 `normalization_window` 参数；滑动窗口变为 `normalization_window`，mean/std 基于该窗口计算，只输出最后 `sequence_length` 行 |
| `models/lstm/classifier.py` | `train()` 中数据加载适配更大窗口；`predict_proba()` 移除内部标准化，由调用方负责 |
| `models/lstm/predictor.py` | 加载 `normalization_window` 天原始数据，用该窗口的 mean/std 归一化最后 `sequence_length` 行，传给 `predict_proba` |
| `models/training/helpers.py` | `_load_year_data` 的 `extra_days` 从布尔开关改为真正控制提前日历天数 |

## 详细设计

### 1. ModelConfig 新增字段

在 `create_config` 函数签名和 `ModelConfig` Document 中新增：

```python
lstm_normalization_window: int = 300
```

`lstm_sequence_length`（60）定义模型输入维度，`lstm_normalization_window`（300）定义标准化统计量的计算窗口。

### 2. helpers.py — `_load_year_data` 改造

当前 `extra_days > 0` 只是布尔开关，决定是否从 `year-1-01-01` 加载。改为按实际天数推算：

```python
async def _load_year_data(year, ts_codes, horizon, extra_days=0):
    # 改后：extra_days 是实际需要的日历缓冲天数
    data_start = (datetime(year, 1, 1) - timedelta(days=extra_days)).strftime("%Y%m%d")
    ...
```

需要约 300 个交易日的原始数据，按 ~250 交易日/年、1.5 倍安全系数，`extra_days` = `int(normalization_window * 1.5)` ≈ 450 日历天，确保年初的股票也有足够数据填满 300 天窗口。

### 3. normalizer.py — `create_sequences` 改造

```python
def create_sequences(df, feature_fields, target_names,
                     sequence_length, normalization_window):
    X_list, y_list = [], []
    for _, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date")
        values = group[feature_fields].values.astype(np.float64)
        labels = group[target_names].values.astype(np.float64)
        if len(values) < normalization_window:
            continue
        # 步进 1 天，滑动 normalization_window 天
        for i in range(normalization_window - 1, len(values)):
            window = values[i - normalization_window + 1 : i + 1].copy()
            label = labels[i]
            if np.isnan(window).any() or np.isnan(label).any():
                continue
            mean = window.mean(axis=0)
            std = window.std(axis=0)
            std[std == 0] = 1.0
            # 整个窗口归一化，只取最后 sequence_length 行
            normed = (window - mean) / std
            seq = normed[-sequence_length:]
            X_list.append(seq)
            y_list.append(label)
    ...
    return np.array(X_list), np.array(y_list)
```

- 滑动步长仍是 1，但窗口大小从 `sequence_length` 变为 `normalization_window`
- mean/std 基于整个 `normalization_window` 计算
- 输出只取 `normed[-sequence_length:]`，X_3d 形状保持 `(样本数, 60, 特征数)`

### 4. classifier.py — 训练适配

```python
# train() 中
seq_len = self.sequence_length                         # 60
norm_window = config.lstm_normalization_window          # 300
extra_days = int(norm_window * 1.5)                     # 450 日历天

# _load_year_data 传 extra_days 已由 helpers.py 改造支持
# create_sequences 传 normalization_window
X_3d, y_2d = create_sequences(
    combined_df, config.feature_fields, target_names,
    sequence_length=seq_len,
    normalization_window=norm_window,
)
```

### 5. classifier.py — `predict_proba` 改造

当前 `predict_proba` 在方法内部用最后 `sequence_length` 行的 mean/std 做标准化。改为接收已归一化的特征，移除此内部标准化：

```python
def predict_proba(self, features, target_names):
    # 输入 features 已由调用方（LSTMPredictor）完成标准化
    seq = np.array(features, dtype=np.float64)
    if len(seq) < self.sequence_length:
        return {t: [0.0, 0.0, 0.0] for t in target_names}
    seq = seq[-self.sequence_length:]
    X_tensor = torch.FloatTensor(seq).unsqueeze(0)
    ...  # 模型推理逻辑保持不变
```

此改动安全的原因：
- `create_sequences` 输出的 X_3d 已归一化，训练阶段评估（train() 第 237-247 行）直接调用 `model()` 而非 `predict_proba`
- `predict_proba` 仅在 `LSTMPredictor` 的外部预测链路中被调用

### 6. predictor.py — 预测适配

```python
class LSTMPredictor(BasePredictor):
    async def predict(self, ts_code, target_names, current_date):
        seq_len = self.config.lstm_sequence_length                  # 60
        norm_win = self.config.lstm_normalization_window             # 300
        df = await self.data_loader.load_history_data(
            current_date, [ts_code], norm_win + seq_len)
        if df.empty:
            return None
        stock = df[df["ts_code"] == ts_code].sort_values("trade_date")
        if len(stock) < norm_win + seq_len:
            return None
        # 取最后 norm_win+seq_len 行，前 norm_win 行算统计量，后 seq_len 行做归一化
        data = stock[self.config.feature_fields].values
        chunk = data[-(norm_win + seq_len):]
        norm_data, feed = chunk[:-seq_len], chunk[-seq_len:]
        mean, std = norm_data.mean(axis=0), norm_data.std(axis=0)
        std[std == 0] = 1.0
        features = (feed - mean) / std
        if np.isnan(features).any():
            return None
        return self.classifier.predict_proba(features, target_names)
```

## 不涉及改动的文件

- `BaseClassifier`/`BasePredictor` 接口不变
- `execution/data_loader.py` 方法签名不变，调用方传更大的 `days` 参数即可
- `execution/pipeline.py`、`models/factory.py` 流程不变

## 测试

- 单元测试验证 `create_sequences` 传入不同 `normalization_window` 时输出形状为 `(N, 60, n_features)`
- 验证用 `normalization_window` 天窗口做标准化的数据均值约 0、标准差约 1
- 集成测试确认训练/预测链路可用
