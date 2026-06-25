# 安全标签 (Safety Label) 训练模式

## 概述

新增第三种标签计算模式 `label_mode="safety"`，替代现有的 threshold/trend 模式。标签定义：N 日内最低价是否跌破当日开盘价，用于预测"买入后不会被止损出局"的概率。

## 三分类规则

每个时间窗口（5d/10d/20d）独立计算 `label_{h}d`：

| 标签 | 含义 | 条件 |
|:---:|:----|:----|
| **+1** | 安全 | N日内最低收盘价 >= 当日开盘价 |
| **0** | 中性 | 其他情况 |
| **-1** | 风险 | N日内最低价 < 当日开盘价 × 0.95 |

数据分布（5d 实测）：安全 ~29%，中性 ~42%，风险 ~29%，接近 30-40-30。

## 改动

仅修改 `models/training/helpers.py`：

### 新增 `_create_safety_labels`

```python
def _create_safety_labels(df: pd.DataFrame, horizons: List[int]) -> pd.DataFrame:
    label_cols = [f"label_{h}d" for h in horizons]
    result_parts = []
    for ts_code, group in df.groupby("ts_code"):
        group = group.sort_values("trade_date").copy()
        for horizon in horizons:
            # Min close in [T+1, T+horizon]
            min_close = group["close"].rolling(horizon).min().shift(-horizon)
            # Min low in [T+1, T+horizon]
            min_low = group["low"].rolling(horizon).min().shift(-horizon)
            col = f"label_{horizon}d"
            group[col] = 0
            group.loc[min_close >= group["open"], col] = 1
            group.loc[min_low < group["open"] * 0.95, col] = -1
        group = group.dropna(subset=label_cols)
        result_parts.append(group)
    return pd.concat(result_parts, ignore_index=True)
```

### `create_labels` 增加分支

```python
def create_labels(df, horizons, label_mode="threshold", ...):
    if label_mode == "trend":
        return _create_trend_labels(df, horizons, ...)
    if label_mode == "safety":
        return _create_safety_labels(df, horizons)
    return _create_classification_labels(df, horizons, ...)
```

其他文件无需改动。`label_mode` 已在模型配置和训练流程中支持，通过 API 切换即可。
