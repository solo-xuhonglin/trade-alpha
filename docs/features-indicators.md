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
| obv | OBV指标（累计净成交量） |
| obv_chg_5 | OBV的5日累计变化 |
| obv_chg_10 | OBV的10日累计变化 |
| obv_chg_20 | OBV的20日累计变化 |

**计算方法**：
- 如果当日收盘价 > 前收盘价：OBV = 前OBV + 当日成交量
- 如果当日收盘价 < 前收盘价：OBV = 前OBV - 当日成交量
- 如果当日收盘价 == 前收盘价：OBV = 前OBV
- obv_chg_N = OBV[t] - OBV[t-N]（N日累计净值变化）

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

## 标签计算方法

### 分类标签（threshold 模式）

根据未来收益是否超过阈值来标记：

| 标签 | 条件 |
|------|------|
| 1（上涨）| 未来 N 天收益率 > 阈值 |
| 0（持平）| -阈值 ≤ 未来 N 天收益率 ≤ 阈值 |
| -1（下跌）| 未来 N 天收益率 < -阈值 |

**默认阈值**：
- label_3d: 1%
- label_5d: 1.5%
- label_10d: 2%

### 趋势标签（trend 模式）

根据均线趋势和技术指标来判断：

| 标签 | 条件 |
|------|------|
| 1（上涨）| 未来收盘价 > 未来均线 AND 未来均线斜率 > 当前均线斜率 AND 未来收益率 > 阈值 |
| 0（持平）| 其他情况 |
| -1（下跌）| 未来收盘价 < 未来均线 AND 未来均线斜率 < 当前均线斜率 AND 未来收益率 < -阈值 |

**均线配置**：
| 周期 | 基准均线 | 斜率均线 | 前移天数 |
|------|---------|---------|---------|
| 3天 | ma_20 | ma_5 | 2 |
| 5天 | ma_40 | ma_10 | 3 |
| 10天 | ma_60 | ma_20 | 5 |

**特点**：
- 使用未来指标判断趋势，避免用当前指标预测未来收益不一致
- 不填充均线数据的 NaN 值，有空值则该行标签为 0

**示例**（label_3d）：
```python
close_future = close.shift(-2)       # 2天后收盘价
ma_20_future = ma_20.shift(-2)       # 2天后ma_20
ma_5_future = ma_5.shift(-2)         # 2天后ma_5

trend_up = (close_future > ma_20_future) & (ma_5_future > ma_5)
label = 1 if trend_up & (ret > threshold) else (-1 if trend_down & (ret < -threshold) else 0)
```

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
- 标签计算：[backend/src/trade_alpha/models/training/helpers.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/models/training/helpers.py)

## 排名优化

回测时对模型原始评分做多种调整，按固定顺序执行。

### 分数体系

```
原始评分 → 原始分 (raw_score)
    ↓
趋势加分 (trend_bonus) - 趋势扣分 (trend_penalty)  动量加成 (momentum_bonus) - 动量扣分 (momentum_penalty)
    ↓
综合分 (composite_score = raw_score + trend_bonus - trend_penalty + momentum_bonus - momentum_penalty)
    ↓
EWMA 平滑 → 排名分 (ranking_score)  仅用于排名，不参与买卖判断
```

- **原始分 (raw_score)**：模型输出的原始概率分数 `score`
- **加减分 (bonuses)**：趋势加分、动量加成各自独立存储，不修改原始分
- **综合分 (composite_score)**：原始分 + 所有加减分，用于买卖阈值判断
- **排名分 (ranking_score)**：综合分的 EWMA 平滑结果，仅用于股票排名（排序）

### 执行顺序

```
原始分 → 趋势加分/扣分 → 动量加成/扣分 → 综合分 → 排名平滑 → 排名分
```

### 1. 趋势加分（Trend Bonus）

基于收盘价的 R² 加权线性回归斜率，识别稳定上涨趋势。

**算法**：对窗口内 N 个收盘价做线性回归，得到斜率 `slope` 和拟合优度 `R²`
- 条件：`slope > 0` 且 `R² ≥ r2_threshold`
- 加分：`bonus = clamp(slope × R² × scale, 0, max_bonus)`
- R² 衡量趋势稳定性，不稳定趋势（R² 低）不加分

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `use_trend_bonus` | bool | false | 是否启用 |
| `trend_bonus_window` | int | 15 | 收盘价回归的窗口天数 |
| `trend_bonus_scale` | float | 0.03 | 斜率放大系数 |
| `trend_r2_threshold` | float | 0.30 | R² 最低门槛 |
| `trend_max_bonus` | float | 0.1 | 加分上限 |

### 2. 趋势扣分（Trend Penalty）

基于收盘价的 R² 加权线性回归斜率，识别下跌趋势并扣分。

**算法**：对窗口内 N 个收盘价做线性回归，得到斜率 `slope` 和拟合优度 `R²`
- 条件：`slope < 0` 且 `R² ≥ trend_penalty_r2_threshold`
- 扣分：`penalty = clamp(|slope| × R² × scale, 0, max_penalty)`
- R² 衡量趋势稳定性，不稳定趋势（R² 低）不扣分

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `use_trend_penalty` | bool | false | 是否启用 |
| `trend_penalty_window` | int | 15 | 收盘价回归的窗口天数 |
| `trend_penalty_scale` | float | 0.03 | 斜率放大系数 |
| `trend_penalty_r2_threshold` | float | 0.30 | R² 最低门槛 |
| `trend_penalty_max_penalty` | float | 0.1 | 扣分上限 |

### 3. 动量调整（Momentum Adjustment）

基于股价的涨跌天数占比进行加成或扣分。

**算法**：统计窗口内收盘价日涨跌，计算上涨天数占比
- `up_ratio = up_days / window`
- `down_ratio = 1 - up_ratio`
- **动量加成**（启用 `use_momentum_boost`）：`bonus = up_ratio × max_momentum_bonus`
- **动量扣分**（启用 `use_momentum_penalty`）：`penalty = down_ratio × max_momentum_penalty`

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `use_momentum_boost` | bool | false | 是否启用动量加成 |
| `use_momentum_penalty` | bool | false | 是否启用动量扣分 |
| `momentum_window` | int | 5 | 动量窗口天数 |
| `max_momentum_bonus` | float | 0.05 | 动量加成上限 |
| `max_momentum_penalty` | float | 0.05 | 动量扣分上限 |

### 5. 排名平滑（Ranking Smoothing）

对综合分做 EWMA 平滑，得到排名分。

**算法**：
- `ranking_score[t] = α × composite_score[t] + (1-α) × ranking_score[t-1]`
- α 由用户指定，为空则自动计算：`α = 2 / (window + 1)`

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `ranking_smooth_window` | int | 3 | EWMA 窗口天数 |
| `ranking_smooth_alpha` | float | 0.5 | 手动指定 α（0~1），为空则用 `2/(window+1)` |

### 6. 暴涨排除（Explosion Filter）

基于价格和成交量的异动排除。

**算法**：当日涨幅 > `price_threshold` 且量比 > `volume_ratio` × 前N日均量时，标记为排除
- 方向判断：`pct_chg_mean` > 0 看涨方向排除，< 0 看跌方向排除
- 排除后的股票不参与排名
- 使用专用字段 `is_explosion_excluded` 标记，与 `is_acceleration_excluded` 互不干扰

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `use_explosion_filter` | bool | false | 是否启用 |
| `explosion_price_threshold` | float | 0.05 | 涨幅阈值（5%） |
| `explosion_volume_ratio` | float | 3.0 | 量比阈值（3倍） |
| `explosion_window` | int | 5 | 均量计算窗口 |

## 市场分析指标

`compute_market_regime()` 在每日决策前计算全市场股票池的统计指标，经 EWMA 平滑后用于市场状态分类和仓位缩放。

### 分数中位数 (ranking_median)

全市场 `ranking_score` 的中位数，反映市场整体评分水平。

- **ranking_median**：当日原始中位数
- **ranking_median_smoothed**：EWMA 平滑后的中位数，用于图表展示市场状态（trending_up / trending_down / sideways）

### 每日重平衡基线 (Daily-Rebalanced Baseline)

根据全市场股票的收盘价每日计算的等权平均收益率，用于市场阶段判断。

- **daily_rebalanced_cum**：等权持有全部股票（每日再平衡）的累计收益率
- **市场阶段**：根据 `dr_5d`（基线5日变化率）和 `low_5d`（低分占比5日变化）划分为4个阶段：
  - `crash`（dr_5d < -6%）：仓位系数=0，空仓避险
  - `decline`（dr_5d < 0 且 low_5d > 0）：仓位系数=0.5，减仓
  - `recovery`（dr_5d < -3% 且 low_5d < 0）：买入系数=0.5，低阈值建仓
  - `normal`：仓位系数=1.0，买入系数=1.0，正常运行

### 排名前N留存率 (Top-N Retention Rate)

D 天前排名前 n 的股票中，当天仍然在前 n 名的比例。衡量市场持续性，参数 `top_n_retention`（N值）和 `retention_days`（天数）可配置。

- **top_n_retention_rate**：当日原始留存率
- **top_n_retention_rate_smoothed**：EWMA 平滑后的留存率

### 评分与收益率关联度 (Score-Return Correlation)

N 日内每只股票 `composite_score` 均值与 `pct_chg` 均值的 Pearson 截面相关系数（排除窗口期内有 `is_excluded` 的股票）。参数 `correlation_window` 控制均值窗口长度。

- **score_return_corr**：当日原始相关系数
- **score_return_corr_smoothed**：EWMA 平滑后的相关系数

### 平滑参数

三个指标的 EWMA 平滑共用同一组参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `market_smooth_window` | int | 5 | EWMA 平滑窗口 |
| `market_smooth_alpha` | float | 0.3 | EWMA 平滑系数 |
| `top_n_retention` | int | 20 | 留存率计算的前 N 名 |
| `retention_days` | int | 5 | 留存天数：D 天前的 top N 到今天还有多少留存 |
| `correlation_window` | int | 5 | 关联度窗口：N 日内平均评分与平均收益率做截面相关 |

## 交易优化

回测时对交易执行过程做额外控制。

### 1. 满仓容忍卖出（Full Position Sell）

当持仓市值占比连续 N 日超过阈值时，强制卖出评分最低的持仓。

**算法**：
- 每日检查 `(total_value - cash) / total_value ≥ threshold`
- 连续满足 N 日后触发，每次卖出 `sell_count` 只评分最低的持仓

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `use_full_position_sell` | bool | false | 是否启用 |
| `full_position_threshold` | float | 0.90 | 持仓占比阈值 |
| `full_position_days` | int | 3 | 连续触发天数 |
| `full_position_sell_count` | int | 1 | 每次卖出数量 |

### 7. 排名上涨优先（Rank-Up Priority Buy）

当启用时，买入决策分为两阶段执行：第一阶段优先买入排名持续上涨的股票，第二阶段用剩余资金按综合评分买入其余股票。

**算法**：

```
两阶段买入流程：

1. 计算 rank_improvement
   - 对每只股票，取最近 rank_up_window 天的历史排名计算均值 rank_avg
   - 与前 window 天的均值 prev_rank_avg 比较
   - improvement = (prev_rank_avg - rank_avg) / prev_rank_avg
   - improvement > 0 表示排名在提升（数值越小排名越靠前）

2. 筛选候选股
   - composite_score >= rank_up_min_score
   - improvement >= rank_up_min_improvement_pct
   - 按 improvement 降序排列，取前 rank_up_count 只

3. 第一阶段：优先买入
   用可用资金依次买入候选股，每只买入受 max_position_pct 限制

4. 第二阶段：常规买入
   用剩余资金，在未买入的股票中按 composite_score 降序买入
```

**rank_improvement 计算**：

```
rank_improvement[t] = (avg_rank_prev_window - avg_rank_current_window) / avg_rank_prev_window

其中：
  avg_rank_current_window = mean(rank[t - window + 1:t + 1])
  avg_rank_prev_window   = mean(rank[t - 2 * window + 1:t - window + 1])

rank_improvement > 0  → 排名在改善（数值变小，排名靠前）
rank_improvement = 0  → 排名不变
rank_improvement < 0  → 排名在恶化
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `use_rank_up_priority` | bool | false | 是否启用排名上涨优先买入 |
| `rank_up_window` | int | 5 | 排名均值窗口天数 |
| `rank_up_count` | int | 3 | 优先买入的股票数量上限 |
| `rank_up_min_score` | float | 0.1 | 最低综合评分门槛 |
| `rank_up_min_improvement_pct` | float | 0.20 | 最小排名提升比例（20%） |

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
