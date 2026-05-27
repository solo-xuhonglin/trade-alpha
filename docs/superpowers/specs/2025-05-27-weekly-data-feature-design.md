# 周线数据特征融合设计

## 概述

从 Tushare 拉取周线（`freq="W"`）数据，独立存储到 `stock_weekly` 集合，计算与日线一致的全套技术指标。在训练数据加载和回测数据加载时，按日期匹配**上周**的周线字段，作为额外特征合并到日线 DataFrame 中参与标准化和训练/预测。

## 数据模型

### StockWeekly

新建 `stock_weekly` 集合，与 `stock_daily` 结构一致。trade_date 为周五日期。

```
Collection: stock_weekly
Index: [(ts_code, 1), (trade_date, -1)]

Fields:
  ts_code: str
  trade_date: str          # YYYYMMDD（周五）
  open / high / low / close / vol / amount: float

  # 均线
  ma_5 / ma_10 / ma_20 / ma_40 / ma_60: Optional[float]

  # MACD
  macd / macd_signal / macd_hist: Optional[float]

  # 自定义指标（全量与日线一致）
  pct_chg: Optional[float]
  bias_5 / bias_10 / bias_20 / bias_60: Optional[float]
  close_position_5 / close_position_10 / close_position_20 / close_position_60: Optional[float]
  vol_ratio_5 / vol_ratio_10 / vol_ratio_20 / vol_ratio_60: Optional[float]
  kdj_k / kdj_d / kdj_j: Optional[float]
  boll_upper / boll_middle / boll_lower / boll_position: Optional[float]
  rsi_6 / rsi_12: Optional[float]

  # 趋势类
  trend_arrangement_5 / trend_arrangement_10 / trend_arrangement_20: Optional[float]
  trend_slope_5 / trend_slope_10 / trend_slope_20: Optional[float]
  trend_volume_5 / trend_volume_10 / trend_volume_20: Optional[float]
  trend_stability_5 / trend_stability_10 / trend_stability_20: Optional[float]

  # OBV
  obv: Optional[float]
  obv_chg_5 / obv_chg_10 / obv_chg_20: Optional[float]

  # K线形态
  candle_body_pct / candle_upper_pct / candle_lower_pct: Optional[float]
  close_location_pct / gap_pct / gap_fill_pct: Optional[float]
```

数据库表名 `stock_weekly`，DAO 模型文件 `backend/src/trade_alpha/dao/stock_weekly.py`。

## 数据获取

### 1. Tushare 拉取

通过 `ts.pro_bar(freq="W")` 拉取周线 OHLCV 数据，与日线相同的复权方式（qfq）。创建 `fetch_stock_weekly_data()` 函数，逻辑与日线 `fetch_stock_data()` 一致，仅 `freq="W"` 不同。

### 2. 入库与删除

新增 `fetch_and_store_stock_weekly()` 和 `delete_stock_weekly_by_ts_code()` 函数，复用日线的 upsert 模式（按 ts_code + trade_date 去重）。

### 3. 同步时机

在 `process_single_stock()` 中，日线拉取和指标计算完成后，追加：
```python
fetch_and_store_stock_weekly() → calculate_all_indicators_weekly() → 更新数据计数
```

## 指标计算

复用现有指标计算函数（`ma.py`、`macd.py`、`custom/*`），所有函数都是纯 DataFrame 计算，与集合无关。

新增 `calculate_all_indicators_weekly(ts_code)`，内部逻辑与日线 `calculate_all_indicators()` 完全一样，只是读写 `stock_weekly` 集合。

## 特征合并

### 1. 周线匹配逻辑

对于日线日期 D（如 `20250312` 周三）：
1. 计算 D 所属周的周五日期 W_friday
2. 查找上周五的周线记录（W_friday - 7 天）
3. 若存在则合并，若不存在则周线字段填 None（标准化时会丢弃）

实现函数 `merge_weekly_features(daily_df: pd.DataFrame, weekly_df: pd.DataFrame) -> pd.DataFrame`：

```python
def merge_weekly_features(daily_df, weekly_df):
    """Merge previous week's weekly features into daily dataframe."""
    daily = daily_df.copy()
    # 计算每个日线日期对应的"上一周周五"
    daily_dt = pd.to_datetime(daily["trade_date"], format="%Y%m%d")
    # 上一周周五 = 当前日期的上周五
    last_friday = daily_dt - pd.to_timedelta(daily_dt.dt.dayofweek + 3, unit="D")
    daily["_week_key"] = last_friday.dt.strftime("%Y%m%d")
    
    weekly = weekly_df.copy()
    weekly["_week_key"] = weekly["trade_date"]
    
    weekly_fields = [c for c in weekly.columns if c not in ["ts_code", "trade_date", "_week_key"]]
    weekly_renamed = {f: f"{f}_w" for f in weekly_fields}
    weekly = weekly.rename(columns=weekly_renamed)
    
    merged = daily.merge(
        weekly[["ts_code", "_week_key", *weekly_renamed.values()]],
        on=["ts_code", "_week_key"],
        how="left",
    )
    merged = merged.drop(columns=["_week_key"])
    return merged
```

### 2. 字段命名

所有周线字段加 `_w` 后缀：
- `close_w`、`ma_5_w`、`macd_w`、`rsi_6_w` ...

用户在 `ModelConfig.feature_fields` 中手动勾选需要的周线字段。

### 3. 影响的代码位置

**训练数据加载** — `helpers.py:_load_year_data()`
- 加载日线数据后，额外加载对应时间范围的周线数据
- 调用 `merge_weekly_features()` 合并

**回测数据加载** — `data_loader.py`
- `load_day_data()`：返回的 DataFrame 中追加周线字段
- `load_history_data()`：同样追加周线字段

## 配置变更

### ModelConfig

无需修改数据模型。用户在界面上勾选 `close_w`、`ma_5_w` 等字段即可。

### 前端配置界面

`ModelConfigView.vue` 已支持从 `featureFields` 列表勾选。只需将 `close_w`、`ma_5_w` 等周线字段加入可选列表即可。

## API 变更

提供基础 CRUD 接口（与日线对称）：
- `GET /data/{ts_code}/weekly` — 查询周线数据
- `POST /data/weekly` — 拉取并存储周线数据（供手动触发）
- `DELETE /data/{ts_code}/weekly` — 删除周线数据

## 数据流总览

```
Tushare pro_bar(freq="W")
    ↓
fetch_and_store_stock_weekly()
    ↓
stock_weekly 集合                stock_daily 集合
    ↓                                ↓
calculate_all_indicators_weekly()    calculate_all_indicators()
    ↓                                ↓
stock_weekly (含指标)              stock_daily (含指标)
    ↓                                ↓
    └─────── merge_weekly_features() ← 匹配上一周
                       ↓
            日线 DataFrame + 周线 _w 字段
                       ↓
              标准化 (normalize/create_sequences)
                       ↓
                  训练 / 预测
```

## 未解决的问题

无。
