# 趋势加分与波动扣分设计文档

## 概述

废除旧的"趋势左移"（基于分数斜率的线性回归），替换为两个独立功能：**趋势加分**和**波动扣分**，均基于实际股价数据计算。

## 核心思路

旧版问题：
- 基于分数斜率，window=5 过于短期
- 仅看方向不看趋势质量（稳定性）
- 短期回调误判为向下跌 → 错误扣分

新版方案：
- 两个功能互相独立，各有独立开关和参数，可单独验证
- **趋势加分**：基于收盘价，R² 加权斜率，识别稳定上涨趋势，短期回调不误判
- **波动扣分**：基于 OHLC（开盘/最高/最低/收盘），用**日内平均振幅**衡量波动剧烈程度

## Pipeline 调用顺序

```
compute_scores (原始分数)
→ _smooth_scores (EWMA)
→ _apply_trend_bonus (趋势加分)        ← 替代旧趋势左移
→ _apply_volatility_penalty (波动扣分)  ← 新增
→ _apply_momentum_boost (动量加成)
→ _filter_explosions (暴涨排除)
→ _record_ranks
```

## 功能一：趋势加分

### 算法：R² 加权线性回归斜率

对 N 天收盘价计算线性回归：

```
对 N 天的收盘价序列 close_prices[0..N-1]
计算线性回归的斜率(slope)和拟合优度(R²)

R² 衡量股价走势是否接近一条直线：
  - R² = 0.90 → 股价几乎笔直上涨 → 加分
  - R² = 0.40 → 有涨有跌但整体向上 → 轻微加分
  - R² = 0.05 → 走势杂乱无章 → 不加分

加分逻辑：
  如果 slope > 0 且 R² ≥ r2_threshold：
    trend_bonus = clamp(slope × R² × bonus_scale, 0, max_bonus)
  否则：
    trend_bonus = 0.0
```

注意：趋势加分**只加分不扣分**。下跌趋势或走势杂乱不触发加分，但不做扣分处理（扣分由波动扣分功能处理）。

### 典型场景（window=10）

| 走势 | 10日价格序列 | slope | R² | 加分 |
|------|------------|-------|-----|------|
| 温和上涨 | 100→102→104→106→108→110→112→114→116→118 | +2.0 | 0.99 | +0.030 |
| 上涨有回调 | 100→103→101→106→104→109→107→112→110→115 | +1.6 | 0.46 | +0.011 |
| 上涨剧烈震荡 | 100→108→92→110→90→112 | +1.2 | 0.08 | 0 |
| 稳定下跌 | 118→116→114→112→110→108 | -2.0 | 0.99 | 0 |
| 横盘 | 100→101→99→102→100→101 | +0.1 | 0.02 | 0 |

### 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `use_trend_bonus` | false | 启用趋势加分 |
| `trend_bonus_window` | 10 | 价格观察窗口（交易日） |
| `trend_bonus_scale` | 0.03 | 斜率→加分的放大系数 |
| `trend_r2_threshold` | 0.30 | R² 低于此值视为趋势不稳，不给加分 |
| `trend_max_bonus` | 0.05 | 最大加分上限 |

## 功能二：波动扣分

### 算法：日内平均振幅（OHLC）

基于 OHLC（Open/High/Low/Close）计算每日振幅比，衡量日内的剧烈程度。

只用收盘价做路径平滑度会**漏掉日内波动**。例如：

```
日期    开盘    最高    最低    收盘
D1      100     108     93      101
D2      101     110     95      102
D3      102     109     94      103
```

收盘价看：101→102→103 稳步上涨 → 不扣分。但每天振幅 7~8% → **应当扣分**。

改进方案：使用**日内振幅比**：

```python
# 每日振幅比 = (最高 - 最低) / 收盘价
daily_ranges = [(high_i - low_i) / close_i for i in range(N)]

# 窗口内平均振幅比
avg_daily_range = mean(daily_ranges)

# 超过容忍阈值则扣分
vol_penalty = clamp((avg_daily_range - range_tolerance) * penalty_scale, 0, max_penalty)
```

### 典型场景（window=10）

| 走势 | 收盘价变化 | 日均振幅 | 扣分 |
|------|-----------|---------|------|
| 温和上涨 | 100→102→104→106→108→110→112→114→116→118 | 1.5% | 0 |
| 震荡但收盘委婉 | 100→102→101→103→102→104→103→105→104→106 | 7.5% | **-0.020** |
| 剧烈震荡 | 108→92→110→90→112→88→115→85→118→82 | 8.2% | **-0.024** |
| 横盘抖动 | 100→101→99→102→100→101→99→102→100→101 | 4.2% | -0.004 |

### 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `use_volatility_penalty` | false | 启用波动扣分 |
| `vol_penalty_window` | 10 | 价格观察窗口 |
| `vol_range_tolerance` | 0.035 | 日均振幅容忍度（默认 3.5%，低于此不扣分） |
| `vol_penalty_scale` | 0.005 | 每超 1% 振幅的扣分力度 |
| `vol_max_penalty` | 0.05 | 最大扣分上限 |

## 两功能叠加效果

| 股票走势 | 趋势加分 | 波动扣分 | 净调整 |
|---------|---------|---------|-------|
| 稳涨：100→102→104→106→108→110→112→114→116→118 | +0.030 | 0 | **+0.030** |
| 震荡向上：105→98→108→102→112→106→115→110→118→112 | +0.010 | -0.006 | **+0.004** |
| 剧烈震荡：108→92→110→90→112→88→115→85→118→82 | 0 | -0.024 | **-0.024** |
| 横盘剧烈：100→108→93→110→90→112→88→115→85→118 | 0 | -0.028 | **-0.028** |

两个功能独立开关，可以组合验证：
- 仅开启趋势加分：观察选股是否更偏好温和上涨的股票
- 仅开启波动扣分：观察是否避开了大起大落的股票
- 同时开启：两者互补

## 数据模型修改

### 删除旧参数

StrategyConfig 中删除：

| 字段 | 原因 |
|------|------|
| `use_trend_boost` | 被 `use_trend_bonus` + `use_volatility_penalty` 替代 |
| `trend_window` | 被 `trend_bonus_window` + `vol_penalty_window` 替代 |
| `trend_scale` | 被 `trend_bonus_scale` + `vol_penalty_scale` 替代 |
| `max_trend_boost` | 被 `trend_max_bonus` + `vol_max_penalty` 替代 |

### 新增参数

| 字段 | 类型 | 默认值 | 所属 | 说明 |
|------|------|--------|------|------|
| `use_trend_bonus` | bool | false | 趋势加分 | 启用趋势加分 |
| `trend_bonus_window` | int | 10 | 趋势加分 | 价格观察窗口 |
| `trend_bonus_scale` | float | 0.03 | 趋势加分 | 斜率放大系数 |
| `trend_r2_threshold` | float | 0.30 | 趋势加分 | R² 阈值 |
| `trend_max_bonus` | float | 0.05 | 趋势加分 | 最大加分上限 |
| `use_volatility_penalty` | bool | false | 波动扣分 | 启用波动扣分 |
| `vol_penalty_window` | int | 10 | 波动扣分 | 价格观察窗口 |
| `vol_range_tolerance` | float | 0.035 | 波动扣分 | 日均振幅容忍度 |
| `vol_penalty_scale` | float | 0.005 | 波动扣分 | 每超 1% 振幅的扣分力度 |
| `vol_max_penalty` | float | 0.05 | 波动扣分 | 最大扣分上限 |

### ScoredStock 新增字段

```python
class ScoredStock:
    # ... 已有字段
    trend_bonus: float = 0.0        # 趋势加分
    vol_penalty: float = 0.0        # 波动扣分
```

### ExecutionDailySnapshot.predictions 新增字段

每个 prediction 对象新增：
- `trend_bonus: float` — 趋势加分值
- `vol_penalty: float` — 波动扣分值
- `price_slope: float` — 股价斜率（用于分析）
- `price_r_squared: float` — 股价 R²（用于分析）
- `price_avg_range: float` — 日均振幅（用于分析）

## Pipeline 修改

### 删除

- `_apply_trend_boost` 整个方法
- `_calc_linear_slope` 辅助函数
- `_score_buffer_trend` 缓冲区

### 新增

```python
def _calc_r_squared(values: List[float]) -> float:
    """Calculate R² (goodness of fit) for linear regression of a list of values."""
    n = len(values)
    if n < 3:
        return 0.0
    x = list(range(n))
    sum_x = sum(x)
    sum_y = sum(values)
    sum_xy = sum(xi * yi for xi, yi in zip(x, values))
    sum_xx = sum(xi * xi for xi in x)
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return 0.0
    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    ss_res = sum((values[i] - (slope * x[i] + intercept)) ** 2 for i in range(n))
    ss_tot = sum((v - sum_y / n) ** 2 for v in values)
    if ss_tot == 0:
        return 0.0
    return max(0.0, 1.0 - ss_res / ss_tot)


def _apply_trend_bonus(self, pred_results: Dict[str, Dict],
                       close_prices: Dict[str, List[float]]) -> None:
    """Apply trend bonus based on price trend R²-weighted slope.

    Rewards stocks with steady upward price trends (high R²).
    Uses actual close prices, not scores.
    """

def _apply_volatility_penalty(self, pred_results: Dict[str, Dict],
                               ohlc_data: Dict[str, List[Dict]]) -> None:
    """Apply volatility penalty based on daily range ratio (OHLC).

    Penalizes stocks with large intraday fluctuations (high avg daily range).
    Uses Open/High/Low/Close data, not just close prices.
    """
```

### 价格数据获取

`_apply_trend_bonus` 需要收盘价序列，`_apply_volatility_penalty` 需要 OHLC 数据。

使用 `self.data_loader.peek_history_data(trade_date, ts_codes, window)` 批量获取，返回 dict `{ts_code: [StockDaily, ...]}`。`StockDaily` 已包含 open/high/low/close 字段。

窗口期取 `max(trend_bonus_window, vol_penalty_window)`，一次查询即可。

```python
lookback = max(self.strategy_config.trend_bonus_window,
               self.strategy_config.vol_penalty_window)
history_data = await self.data_loader.peek_history_data(
    trade_date, list(pred_results.keys()), lookback
)

close_prices: Dict[str, List[float]] = {}
ohlc_data: Dict[str, List[Dict]] = {}
for ts_code, records in history_data.items():
    close_prices[ts_code] = [r.close for r in records if r.close is not None]
    ohlc_data[ts_code] = [
        {"open": r.open, "high": r.high, "low": r.low, "close": r.close}
        for r in records if r.close is not None
    ]
```

## API 修改

### StrategyConfig API

- "排名优化"区域替换旧的趋势左移配置为两个新配置区块
- `StrategyCreateRequest` 新增 10 个字段，删除旧 4 个字段

### 回测记录 API

`get_backtest_results` 的 `strategy_snapshot` 中自动包含新字段（mongodb 文档存储，不需要额外处理）。

## 前端配置页面修改

删除旧的"趋势左移"区块，新增两个独立配置区块：

### 趋势加分区块

参照动量加成的 UI 模式：

```
[v-switch: 趋势加分] [chip: 基于股价趋势的稳定加分]

窗口天数: [10]    加分系数: [0.03]    R²阈值: [0.30]    最大加分: [0.05]
```

### 波动扣分区块

```
[v-switch: 波动扣分] [chip: 识别日内剧烈波动并减分]

窗口天数: [10]    振幅容忍度: [0.035]    扣分力度: [0.005]    最大扣分: [0.05]
```

### 回测历史配置弹窗

`strategy_snapshot` 中如果有新字段，左侧面板自动显示。无需额外修改。

## 数据迁移

旧版 `use_trend_boost` 字段在已存储的策略配置中会自动忽略（新代码不再读取）。已存储的回测结果的 `StrategySnapshotEmbed` 中的旧 `use_trend_boost` 字段不影响任何逻辑。

旧数据无需迁移，新策略创建时会使用新的字段默认值。

## 实现考虑

1. 价格数据在同一交易日内对所有股票是一次性批量获取，调用一次 `peek_history_data` 即可
2. 窗口期 = `max(trend_bonus_window, vol_penalty_window)`，避免重复查询
3. `_calc_r_squared` 复用现有 `_calc_linear_slope` 的计算结果（增加 R² 计算，不重复计算斜率）
4. 两个功能都不依赖 score 缓冲区，不需要 `_score_buffer_trend`
5. 前端的回测历史弹窗中，"排名优化"区域需要同时展示趋势加分和波动扣分的参数详情