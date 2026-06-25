# 安全标签 (Safety Label) 训练模式

## 概述

新增第三种标签计算模式 `label_mode="safety"`。标签定义：N 日内的最低价是否跌破 T 日 MA5 均线，用于预测"买入后不会被止损出局"的概率。使用 MA5 替代开盘价作为基准，可减少标签分布随周期偏移的问题。

## 三分类规则

每个时间窗口（3d/5d/10d/20d）独立计算 `label_{h}d`：

| 标签 | 含义 | 条件 |
|:---:|:----|:----|
| **+1** | 安全 | N日内最低收盘价 >= T日MA5 × safe_factor |
| **0** | 中性 | 其他情况 |
| **-1** | 风险 | N日内最低价 < T日MA5 × risky_factor |

因子按 horizon 不同，确保各周期分布接近 30-40-30：

| 周期 | safe_factor | risky_factor | 预期分布 S:N:R |
|:---:|:----------:|:-----------:|:-------------:|
| 3d | 1.00 | 0.96 | 35-35-30 |
| 5d | 1.00 | 0.95 | 28-42-30 |
| 10d | 0.99 | 0.93 | 30-40-30 |
| 20d | 0.98 | 0.90 | 30-42-29 |

## 改动

仅修改 `models/training/helpers.py`：

### `_create_safety_labels`

```python
def _create_safety_labels(df: pd.DataFrame, horizons: List[int]) -> pd.DataFrame:
    SAFE_FACTOR = {3: 1.00, 5: 1.00, 10: 0.99, 20: 0.98}
    RISKY_FACTOR = {3: 0.96, 5: 0.95, 10: 0.93, 20: 0.90}
    label_cols = [f"label_{h}d" for h in horizons]
    result_parts = []
    for ts_code, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date").copy()
        for horizon in horizons:
            min_close = group["close"].rolling(horizon).min().shift(-horizon)
            min_low = group["low"].rolling(horizon).min().shift(-horizon)
            col = f"label_{horizon}d"
            group[col] = 0
            group.loc[min_close >= group["ma_5"] * SAFE_FACTOR.get(horizon, 1.0), col] = 1
            group.loc[min_low < group["ma_5"] * RISKY_FACTOR.get(horizon, 1.0), col] = -1
        group = group.dropna(subset=label_cols)
        result_parts.append(group)
    return pd.concat(result_parts, ignore_index=True)
```

### `create_labels` 分支

```python
def create_labels(df, horizons, label_mode="threshold", ...):
    if label_mode == "trend":
        return _create_trend_labels(df, horizons, ...)
    if label_mode == "safety":
        return _create_safety_labels(df, horizons)
    return _create_classification_labels(df, horizons, ...)
```
