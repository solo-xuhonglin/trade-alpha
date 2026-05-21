# 股票字段与技术指标说明

本文档详细说明了 trade-alpha 项目中使用的股票字段和技术指标。

## 股票日线数据字段

### Tushare 原始字段

| 字段名 | 类型 | 说明 |
|--------|------|------|
| ts_code | string | 股票代码 |
| trade_date | string | 交易日期 (YYYYMMDD) |
| open | float | 开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| close | float | 收盘价 |
| pre_close | float | 昨收价 |
| vol | float | 成交量（手） |
| amount | float | 成交额（千元） |

### 技术指标字段

#### 均线指标 (MA)

| 字段名 | 说明 | 计算周期 |
|--------|------|---------|
| ma_5 | 5日均线 | 5天 |
| ma_10 | 10日均线 | 10天 |
| ma_20 | 20日均线 | 20天 |
| ma_60 | 60日均线 | 60天 |

**计算方法**：简单移动平均（SMA）
- ma_n = (close_1 + close_2 + ... + close_n) / n

#### MACD 指标

| 字段名 | 说明 |
|--------|------|
| macd | MACD 柱状值（DIF） |
| macd_signal | MACD 信号线（DEA） |
| macd_hist | MACD 柱状图（MACD - Signal） |

**计算方法**：
- EMA_12 = 收盘价的12日指数移动平均
- EMA_26 = 收盘价的26日指数移动平均
- DIF = EMA_12 - EMA_26
- DEA = DIF的9日指数移动平均
- MACD = (DIF - DEA) * 2

#### 涨跌幅与乖离率

| 字段名 | 说明 | 计算周期 |
|--------|------|---------|
| pct_chg | 涨跌幅（%） | 当日 |
| bias_5 | 5日乖离率 | 5天 |
| bias_10 | 10日乖离率 | 10天 |
| bias_20 | 20日乖离率 | 20天 |
| bias_60 | 60日乖离率 | 60天 |

**计算方法**：
- pct_chg = (close - pre_close) / pre_close * 100
- bias_n = (close - ma_n) / ma_n * 100

#### 收盘价位置

| 字段名 | 说明 | 计算周期 |
|--------|------|---------|
| close_position_5 | 5日收盘价位置 | 5天 |
| close_position_10 | 10日收盘价位置 | 10天 |
| close_position_20 | 20日收盘价位置 | 20天 |
| close_position_60 | 60日收盘价位置 | 60天 |

**计算方法**：当前收盘价在过去n天最高价和最低价之间的百分比位置（0-100之间）
- close_position_n = (close - min_low_n) / (max_high_n - min_low_n) * 100
- 其中 min_low_n 为过去n天最低价，max_high_n 为过去n天最高价

#### 成交量比率

| 字段名 | 说明 | 计算周期 |
|--------|------|---------|
| vol_ratio_5 | 5日成交量比率 | 5天 |
| vol_ratio_10 | 10日成交量比率 | 10天 |
| vol_ratio_20 | 20日成交量比率 | 20天 |
| vol_ratio_60 | 60日成交量比率 | 60天 |

**计算方法**：当前成交量 / 过去n天平均成交量

#### KDJ 随机指标

| 字段名 | 说明 |
|--------|------|
| kdj_k | KDJ K值 |
| kdj_d | KDJ D值 |
| kdj_j | KDJ J值 |

**计算方法**：
- RSV = (close - min_low) / (max_high - min_low) * 100
- K = SMA(RSV, 3)
- D = SMA(K, 3)
- J = 3K - 2D
- 其中 min_low/max_high 为最近9天的最低价/最高价

#### 布林带指标

| 字段名 | 说明 |
|--------|------|
| boll_upper | 布林带上轨 |
| boll_middle | 布林带中轨 |
| boll_lower | 布林带下轨 |
| boll_position | 收盘价在布林带中的位置 |

**计算方法**（参数n=20, k=2）：
- boll_middle = MA_20
- std = 20日收盘价标准差
- boll_upper = MA_20 + k * std
- boll_lower = MA_20 - k * std
- boll_position = (close - boll_lower) / (boll_upper - boll_lower)

#### RSI 相对强弱指标

| 字段名 | 说明 | 计算周期 |
|--------|------|---------|
| rsi_6 | RSI指标 | 6天 |
| rsi_12 | RSI指标 | 12天 |

**计算方法**：
- 计算每日涨跌：up = max(close - pre_close, 0), down = max(pre_close - close, 0)
- 计算n日平均涨跌：avg_up, avg_down
- RS = avg_up / avg_down
- RSI = 100 - 100 / (1 + RS)

#### ATR 平均真实波幅

| 字段名 | 说明 | 计算周期 |
|--------|------|---------|
| atr_14 | ATR指标 | 14天 |

**计算方法**：
- 真实波幅 TR = max(high - low, |high - pre_close|, |low - pre_close|)
- ATR = 14日TR的简单移动平均

#### OBV 能量潮指标

| 字段名 | 说明 |
|--------|------|
| obv | OBV指标 |

**计算方法**：
- 如果当日收盘价 > 前收盘价：OBV = 前OBV + 当日成交量
- 如果当日收盘价 < 前收盘价：OBV = 前OBV - 当日成交量
- 如果当日收盘价 == 前收盘价：OBV = 前OBV

#### K线形态指标

| 字段名 | 说明 | 范围 |
|--------|------|------|
| candle_body_pct | 实体长度占当日振幅百分比 | [0, 100] |
| candle_upper_pct | 上影线长度占当日振幅百分比 | [0, 100] |
| candle_lower_pct | 下影线长度占当日振幅百分比 | [0, 100] |
| close_location_pct | 收盘价在当日区间的位置百分比 | [0, 100] |
| gap_pct | 跳空幅度（正为向上，负为向下） | (-∞, +∞) |
| gap_fill_pct | 跳空回补程度 | [0, 100] |

**计算方法**：
- candle_body_pct = abs(close - open) / (high - low) * 100
- candle_upper_pct = (high - max(open, close)) / (high - low) * 100
- candle_lower_pct = (min(open, close) - low) / (high - low) * 100
- close_location_pct = (close - low) / (high - low) * 100
- gap_pct = (open - prev_close) / prev_close * 100

## 默认配置字段

### 模型配置默认特征字段

当创建模型配置时，默认包含以下特征字段：
```
[
  "ma_5", "ma_10", "ma_20", "ma_60",
  "macd", "macd_signal", "macd_hist",
  "pct_chg",
  "bias_5", "bias_10", "bias_20", "bias_60",
  "close_position_5", "close_position_10", "close_position_20", "close_position_60",
  "vol_ratio_5", "vol_ratio_10", "vol_ratio_20", "vol_ratio_60",
  "kdj_k", "kdj_d", "kdj_j",
  "boll_upper", "boll_middle", "boll_lower", "boll_position",
  "rsi_6", "rsi_12",
  "atr_14",
  "obv"
]
```

## 数据库索引

### stock_daily 表索引

| 索引名 | 字段 | 说明 |
|--------|------|------|
| ts_code_trade_date_idx | ts_code, trade_date | 唯一复合索引 |

## 指标计算顺序

指标计算按照以下顺序执行，确保依赖关系正确：

1. `pct_chg`（涨跌幅）
2. `bias`（乖离率，依赖 MA）
3. `close_position`（收盘价位置）
4. `vol_ratio`（成交量比率）
5. `kdj`（KDJ指标）
6. `boll`（布林带）
7. `rsi`（RSI指标）
8. `atr`（ATR指标）
9. `obv`（OBV指标）

## 相关文件

- 指标定义：[backend/src/trade_alpha/indicators/](file:///d:/projects/trade-alpha/backend/src/trade-alpha/indicators)
- 数据模型：[backend/src/trade_alpha/dao/stock_daily.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/dao/stock_daily.py)
- 服务接口：[backend/src/trade_alpha/indicators/service.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/indicators/service.py)