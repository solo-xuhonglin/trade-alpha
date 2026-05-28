# 动态周线基本特征设计

## 概述

在日线指标计算流程中，从日线数据动态聚合周线基本特征（OHLC + 日均量额），直接写入 `stock_daily` 文档的附加字段。不引入新集合、新 API、新数据源。

## 字段定义

| 字段名 | 类型 | 含义 | 计算方式 |
|--------|------|------|---------|
| `week_open` | float | 本周第一个交易日的开盘价 | 按 (year, week) 分组，取组内首行 open |
| `week_high` | float | 本周至今的最高价 | 组内 expanding max of high |
| `week_low` | float | 本周至今的最低价 | 组内 expanding min of low |
| `week_close` | float | 当日收盘价 | 同 daily close（不额外计算） |
| `week_vol_avg` | float | 本周日均成交量 | 组内累计 vol / 组内交易日数 |
| `week_amount_avg` | float | 本周日均成交额 | 组内累计 amount / 组内交易日数 |

## 实现方案

### 数据流

```
加载所有 StockDaily 记录 → DataFrame
    ↓
按 ts_code 分组 + sort_values("trade_date")
    ↓
提取 (year, week) 列用于周分组
    ↓
逐组计算 expanding 值
    ↓
写入 stock_daily 文档
```

### 涉及文件

| 文件 | 改动 |
|------|------|
| `dao/stock_daily.py` | 新增 6 个 `Optional[float]` 字段 |
| `indicators/custom.py` | 新增 `calculate_weekly_basic_features(df)` 函数 |
| `indicators/service.py` | `calculate_and_store_custom_indicators` 末尾调用周线函数 |
| `frontend/src/api/featureFields.ts` | 新增到 `DAILY_BASIC_FIELDS`（可选，可作为日线基本扩展字段） |

### 实现细节

`calculate_weekly_basic_features(df: pd.DataFrame) -> pd.DataFrame`:

```python
def calculate_weekly_basic_features(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate weekly basic features from daily data (dynamic, no external source)."""
    df = df.copy()
    trade_dates = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    df["week_year"] = trade_dates.dt.isocalendar().year.astype(int)
    df["week_num"] = trade_dates.dt.isocalendar().week.astype(int)

    result = []
    for (year, week), group in df.groupby(["week_year", "week_num"], sort=False):
        group = group.reset_index(drop=True)
        expanding_high = group["high"].expanding().max()
        expanding_low = group["low"].expanding().min()
        cumsum_vol = group["vol"].expanding().sum()
        cumsum_amount = group["amount"].expanding().sum()
        day_count = pd.Series(range(1, len(group) + 1), index=group.index)

        for i in range(len(group)):
            group.at[group.index[i], "week_open"] = group["open"].iloc[0]
            group.at[group.index[i], "week_high"] = expanding_high.iloc[i]
            group.at[group.index[i], "week_low"] = expanding_low.iloc[i]
            group.at[group.index[i], "week_close"] = group["close"].iloc[i]
            group.at[group.index[i], "week_vol_avg"] = cumsum_vol.iloc[i] / day_count.iloc[i]
            group.at[group.index[i], "week_amount_avg"] = cumsum_amount.iloc[i] / day_count.iloc[i]

        result.append(group)

    df = pd.concat(result).drop(columns=["week_year", "week_num"])
    return df
```

### 前端字段

在 `featureFields.ts` 中，新增到 `DAILY_BASIC_FIELDS`：

```typescript
export const DAILY_BASIC_FIELDS = [
  'open', 'high', 'low', 'close', 'vol', 'amount',
  'week_open', 'week_high', 'week_low', 'week_close',
  'week_vol_avg', 'week_amount_avg',
]
```

### 非功能项

- 数据库不创建新集合，仅扩充 stock_daily 文档字段
- 不新增 API 端点
- 不影响已有模型配置（字段名与旧的 `_w` 后缀不同，互不干扰）
- 指标重算时自动重新计算周线特征（幂等）
- 之前已存在的 stock_daily 记录，重跑 `calculate_all_indicators` 即可补全