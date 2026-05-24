# LSTM 标准化窗口分离设计

## 背景

当前 LSTM `create_sequences` 在 `sequence_length`（默认 60）天的小窗口内独立做 Z-score 归一化。每个窗口用自身 60 天的 mean/std 归一化，等价于独立的子序列，丢失了跨窗口的趋势和相对位置信息。

## 目标

将标准化窗口从序列长度中分离出来，标准化统计量基于更大的窗口计算，但只输出最后 `sequence_length` 天的序列，保留价格在大背景下的相对位置。

## 改动汇总

| 文件 | 改动 |
|------|------|
| `models/training/config.py` | 新增 `lstm_normalization_window` 字段，默认 300 |
| `models/lstm/normalizer.py` | `create_sequences` 新增 `normalization_window` 参数；用 `normalization_window` 天计算 mean/std，只输出最后 `sequence_length` 行 |
| `models/lstm/classifier.py` | `train()` 中 `extra_days` 从 `seq_len + 10` 改为 `config.lstm_normalization_window`；调用 `create_sequences` 传入 `normalization_window` |
| `models/lstm/predictor.py` | 预测时从 300 天历史数据中截取后 60 天序列，用这 300 天的 mean/std 归一化 |

**不涉及改动的文件**：
- `BaseClassifier` / `BasePredictor` 接口不变
- `execution/data_loader.py` 方法签名不变，调用方传更大 `days` 即可
- `execution/pipeline.py` 流程不变

## 详细设计

### 1. ModelConfig 新增字段

在 `models/training/config.py` 的 `create_config` 函数参数列表新增：

```python
lstm_normalization_window: int = 300
```

同时在 `ModelConfig` Document 和 `DEFAULT_LSTM_CONFIG` 中添加。

### 2. normalizer.py 改造

```python
def create_sequences(
    df: pd.DataFrame,
    feature_fields: List[str],
    target_names: List[str],
    sequence_length: int,
    normalization_window: int,
) -> Tuple[np.ndarray, np.ndarray]:
    X_3d, y_2d = [], []
    for ts_code, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date")
        values = group[feature_fields].values
        labels = group[target_names].values
        n = len(group)
        # 跳过不足 normalization_window 天的股票
        if n < normalization_window:
            continue
        # 步进 1 天，滑动 normalization_window 天
        for i in range(normalization_window - 1, n):
            window = values[i - normalization_window + 1 : i + 1]
            mean = window.mean(axis=0)
            std = window.std(axis=0)
            std[std == 0] = 1.0
            # 整个窗口归一化，只取最后 sequence_length 行
            normed = (window - mean) / std
            seq = normed[-sequence_length:]
            X_3d.append(seq)
            y_2d.append(labels[i])
    return np.array(X_3d), np.array(y_2d)
```

- 滑动窗口从 `sequence_length` 变为 `normalization_window`
- mean/std 基于整个 `normalization_window` 计算
- 输出只取 `normed[-sequence_length:]`，保证 X_3d 形状不变

### 3. classifier.py 联动

```python
# 改前
seq_len = self.sequence_length  # 60
extra_days = seq_len + 10  # 70

# 改后
seq_len = self.sequence_length       # 60
norm_window = config.lstm_normalization_window  # 300
extra_days = norm_window + seq_len   # 360，确保有足够数据做窗口起始

# 调用 create_sequences 时传入
X_3d, y_2d = create_sequences(
    combined_df, config.feature_fields, target_names,
    sequence_length=seq_len,
    normalization_window=norm_window,
)
```

### 4. predictor.py 联动

`LSTMPredictor` 当前用 `load_history_data(end_date, [ts_code], days=seq_len)`，改为：

```python
norm_window = config.lstm_normalization_window
df = await self.data_loader.load_history_data(end_date, [ts_code], days=norm_window)
```

特征提取时用前 `norm_window` 天计算 mean/std，取最后 `sequence_length` 行：

```python
values = df[feature_fields].values
mean = values.mean(axis=0)
std = values.std(axis=0)
std[std == 0] = 1.0
normed = (values - mean) / std
seq = normed[-sequence_length:]
```

这样保证训练和预测用一致的标准化方式。

### 5. error threshold 

前 `normalization_window - sequence_length - 1` 行的标签在序列滑动到足够数据后才有值，因为 `_create_classification_labels` 依赖未来 horizon 天的数据，标签本身是完整的，只是 `create_sequences` 会跳过不足 `normalization_window` 的尾部。这个行为与之前一致，只是阈值从 `sequence_length` 变成了 `normalization_window`，样本数会略少。

## 测试

- 单元测试验证 `create_sequences` 传入不同 `normalization_window` 时输出形状正确
- 标准化均值约 0、标准差约 1（对 normalization_window 内的数据）
- 集成测试确认训练/预测链路可用
