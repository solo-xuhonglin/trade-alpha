# 股票字段与技术指标说明

本文档详细说明了 trade-alpha 项目中使用的股票字段和技术指标。

## 股票日线数据字段

### 原始数据字段

| 字段名 | 类型 | 说明 |
|--------|------|------|
| ts_code | string | 股票代码 |
| trade_date | string | 交易日期 (YYYYMMDD) |
| open | float | 开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| close | float | 收盘价 |
| vol | float | 成交量（手） |
| amount | float | 成交额（千元） |

### 计算指标字段

#### 均线指标 (MA)

| 字段名 | 说明 | 计算周期 |
|--------|------|---------|
| ma_5 | 5日均线 | 5天 |
| ma_10 | 10日均线 | 10天 |
| ma_20 | 20日均线 | 20天 |
| ma_40 | 40日均线 | 40天 |
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

#### 趋势指标

| 字段名 | 说明 | 计算周期 |
|--------|------|---------|
| trend_arrangement_5 | 5日均线相对20日均线的偏离程度 | 5天 |
| trend_arrangement_10 | 10日均线相对20日均线的偏离程度 | 10天 |
| trend_arrangement_20 | 20日均线相对60日均线的偏离程度 | 20天 |
| trend_slope_5 | 5日均线斜率 | 5天 |
| trend_slope_10 | 10日均线斜率 | 10天 |
| trend_slope_20 | 20日均线斜率 | 20天 |
| trend_volume_5 | 5日价量相关程度 | 5天 |
| trend_volume_10 | 10日价量相关程度 | 10天 |
| trend_volume_20 | 20日价量相关程度 | 20天 |
| trend_stability_5 | 5日趋势稳定程度 | 5天 |
| trend_stability_10 | 10日趋势稳定程度 | 10天 |
| trend_stability_20 | 20日趋势稳定程度 | 20天 |

**计算方法**：
- trend_arrangement_n = (ma_short / ma_long - 1) * 100
- trend_slope_n = (ma_n - ma_n_prev) / ma_n_prev * 100
- trend_volume_n = corr(pct_chg, vol_ratio_n) * 100
- trend_stability_n = 100 - mean(|close - ma_n| / ma_n) * 100

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
  "trend_arrangement_5", "trend_arrangement_10", "trend_arrangement_20",
  "trend_slope_5", "trend_slope_10", "trend_slope_20",
  "trend_volume_5", "trend_volume_10", "trend_volume_20",
  "trend_stability_5", "trend_stability_10", "trend_stability_20",
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
10. `trend`（趋势指标，依赖 ma_*, pct_chg, vol_ratio_*）

## 相关文件

- 指标定义：[backend/src/trade_alpha/indicators/](file:///d:/projects/trade-alpha/backend/src/trade-alpha/indicators)
- 数据模型：[backend/src/trade_alpha/dao/stock_daily.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/dao/stock_daily.py)
- 服务接口：[backend/src/trade_alpha/indicators/service.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/indicators/service.py)

## 指标与价格绝对值关系分析

本部分分析各个技术指标是否受股票价格绝对值影响。

### 判定标准

- **受价格绝对值影响**：指标值与股价绝对值相关，高价股和低价股的同一指标值不可直接比较
- **不受价格绝对值影响**：指标是相对值（百分比、比例、位置），不同价格区间的股票指标值可比

### 指标分类

| 指标类别 | 指标 | 受价格绝对值影响 | 说明 |
|---------|------|-----------------|------|
| **均线指标** | `ma_5`, `ma_10`, `ma_20`, `ma_60` | 是 | 直接是收盘价的算术平均 |
| **MACD** | `macd`, `macd_signal`, `macd_hist` | 是 | EMA差值基于价格计算 |
| **涨跌幅** | `pct_chg` | 否 | 百分比变化 |
| **乖离率** | `bias_5`, `bias_10`, `bias_20`, `bias_60` | 否 | (收盘价 - 均线) / 均线 × 100 |
| **收盘价位置** | `close_position_5`, `close_position_10`, `close_position_20`, `close_position_60` | 否 | 在高低区间的百分比位置 |
| **量比** | `vol_ratio_5`, `vol_ratio_10`, `vol_ratio_20`, `vol_ratio_60` | 否 | 成交量比例 |
| **KDJ** | `kdj_k`, `kdj_d`, `kdj_j` | 否 | RSV = (收盘价 - 最低价)/(最高价 - 最低价) × 100 |
| **布林带** | `boll_upper`, `boll_middle`, `boll_lower` | 是 | 基于价格和标准差 |
| **布林位置** | `boll_position` | 否 | (收盘价 - 下轨)/(上轨 - 下轨) |
| **RSI** | `rsi_6`, `rsi_12` | 否 | 基于涨跌幅比例 |
| **ATR** | `atr_14` | 是 | 真实波幅平均 |
| **OBV** | `obv` | 否 | 只看涨跌方向，加/减成交量 |
| **K线形态** | `candle_body_pct`, `candle_upper_pct`, `candle_lower_pct`, `close_location_pct`, `gap_pct`, `gap_fill_pct` | 否 | 都是百分比或比例 |

### 模型特征推荐

不同模型类型对特征的适应性不同，以下分别给出建议。

#### XGBoost 推荐

XGBoost 使用**截面标准化**（按交易日分组 Z-score），同一天所有股票的特征一起标准化，保留股票间的相对排序。

| 推荐级别 | 特征 | 理由 |
|---------|------|------|
| **强烈推荐** | `close_position_*`, `vol_ratio_*`, `boll_position`, `trend_arrangement_*`, `trend_slope_*` | 截面相对特征，树模型易据此做分裂决策 |
| **推荐** | `rsi_*`, `macd`, `macd_signal`, `macd_hist`, `kdj_k`, `kdj_d`, `kdj_j`, `pct_chg` | 标准化后跨股票可比，适合树模型 |
| **推荐** | `bias_*` | 与价格无关的相对值 |
| **推荐** | `candle_*`, `close_location_pct` | 百分比值，天然适合截面比较 |
| **需注意** | `ma_*`, `macd_*`, `boll_upper/middle/lower`, `atr_14` | 受价格绝对值影响，但截面标准化后可消除量纲差异 |
| **不推荐** | `open`, `close`, `vol`, `amount`（原始字段） | 不同股票量级差异巨大，即使标准化也未必有稳定预测关系 |

#### LSTM 推荐

LSTM 使用**滑动窗口标准化**（按序列窗口 Z-score），每个 `sequence_length` 天（默认60天）的窗口内独立归一化，截面排序信息会丢失。LSTM 适合学习特征的时序演变模式。

| 推荐级别 | 特征 | 理由 |
|---------|------|------|
| **强烈推荐** | `macd`, `macd_hist`, `rsi_*`, `kdj_k`, `kdj_d`, `kdj_j`, `boll_position`, `pct_chg` | 在时间轴上呈现连续轨道变化，LSTM 可学习形态模式 |
| **推荐** | `ma_*`, `bias_*`, `boll_upper/middle/lower` | 窗口内呈现平滑趋势，可捕捉趋势强度变化 |
| **推荐** | `candle_*`, `close_location_pct`, `gap_pct`, `gap_fill_pct` | K线形态天然具有时序延续性 |
| **弱推荐** | `atr_14`, `obv` | 时序上有结构，但量级不稳定 |
| **需注意** | `close_position_*` | 截面排序特征，窗口标准化后失去跨股票比较意义 |
| **需注意** | `trend_arrangement_*` | 离散值（-1/0/1），窗口标准化后失去意义 |
| **需注意** | `vol_ratio_*` | 单股票时序上波动较大，窗口标准化后信噪比低 |
| **需注意** | `trend_stability_*` | 窗口内方差小，标准化后接近零，信息量不足 |
| **注意缺失值** | 所有特征 | 任何 NaN 会丢弃整个60天窗口，造成数据浪费 |

#### 模型差异总结

| 维度 | XGBoost | LSTM |
|------|---------|------|
| **标准化方式** | 截面 Z-score（按交易日） | 窗口 Z-score（按 `normalization_window` 天，默认 300 天） |
| **输入形状** | 2D: (样本, 特征) | 3D: (序列数, `sequence_length`, 特征) |
| **最小数据要求** | 仅需1天数据即可预测 | 需连续 `normalization_window` 天数据才能标准化 |
| **缺失值敏感度** | 低（仅丢弃缺失行） | 高（一个 NaN 丢弃整个窗口） |
| **特征重要性** | 内置（分裂增益） | 无（需 SHAP 等外部工具） |
| **强项特征** | 截面相对特征 | 时序演变特征 |