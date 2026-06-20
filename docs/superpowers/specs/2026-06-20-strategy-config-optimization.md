# 策略配置优化设计方案

## 概述

基于 `default_strategy_live_long` 数据库配置更新后端/前端默认值，移除冗余策略配置判空，清理老旧参数，新增百分比排名参数。

## 一、冗余判空清理

### `scoring.py` — `_load_close_prices_hist`

当前代码：

```python
sell_rank_n = getattr(self._strategy_config, 'sell_rank_n', 15) if self._strategy_config else 15
lookback = sell_rank_n
if self._strategy_config:
    if self._strategy_config.use_trend_bonus:
        lookback = max(lookback, self._strategy_config.trend_bonus_window)
    if self._strategy_config.use_momentum_boost:
        lookback = max(lookback, self._strategy_config.momentum_window)
```

改为（`strategy_config` 始终有值，无需 `if`）：

```python
lookback = 15
if self._strategy_config.use_trend_bonus:
    lookback = max(lookback, self._strategy_config.trend_bonus_window)
if self._strategy_config.use_momentum_boost:
    lookback = max(lookback, self._strategy_config.momentum_window)
```

### `backtest_pipeline.py` — `__init__`

```python
max_positions=getattr(strategy_config, 'max_positions', 10),
max_position_pct=getattr(strategy_config, 'max_position_pct', 0.3),
min_order_value=getattr(strategy_config, 'min_order_value', 5000.0),
atr_stop_multiplier=getattr(strategy_config, 'atr_stop_multiplier', 3.0),
atr_trail_rate=getattr(strategy_config, 'atr_trail_rate', 0.5),
```

`strategy_config` 在构造函数中就传入，这些 `getattr` 兜底多余，直接访问字段：

```python
max_positions=strategy_config.max_positions,
max_position_pct=strategy_config.max_position_pct,
...
```

### `suggestion_pipeline.py` — `__init__`

```python
getattr(self.strategy_config, 'trend_bonus_window', 0) if self.strategy_config and self.strategy_config.use_trend_bonus else 0,
```

改为：

```python
self.strategy_config.trend_bonus_window if self.strategy_config.use_trend_bonus else 0,
```

### `market_regime.py`

```python
n = getattr(self._strategy_config, "top_n_retention", 20)
```

改为直接访问字段（去掉 getattr 兜底）。

## 二、新默认值（来自 `default_strategy_live_long`）

### 后端模型默认值变更

| 字段 | 当前默认 | 新默认 | 说明 |
|------|---------|-------|------|
| `min_order_value` | 5000.0 | **50000.0** | 最小订单金额 |
| `max_hold_days` | 120 | **180** | 最大持仓天数 |
| `buy_threshold` | 0.2 | **0.3** | 买入阈值 |
| `sell_threshold` | -0.01 | **-0.05** | 卖出阈值 |
| `max_positions` | 10 | **6** | 最大持仓数 |
| `max_position_pct` | 0.1 | **0.2** | 单票最大仓位 |
| `use_momentum_boost` | false | **true** | 动量加权 |
| `use_momentum_penalty` | — | **true** | 新增：动量扣分 |
| `use_explosion_filter` | false | **true** | 暴涨排除 |
| `use_trend_bonus` | false | **true** | 趋势加分 |
| `use_trend_penalty` | — | **true** | 新增：趋势扣分 |
| `use_full_position_sell` | false | **true** | 满仓容忍卖出 |
| `full_position_score_window` | 10 | **15** | 满仓评分窗口 |
| `use_rank_up_priority` | false | **true** | 排名上涨优先买入 |
| `rank_up_window` | 5 | **3** | 排名上涨窗口 |
| `rank_up_count` | 3 | **1** | 排名上涨买入数 |
| `rank_up_min_score` | 0.1 | **-0.1** | 排名上涨最低评分 |
| `rank_up_min_improvement_pct` | 0.20 | **0.15** | 排名上涨最小改善 |
| `use_score_decline_filter` | false | **true** | 评分下滑过滤 |
| `market_smooth_window` | 5 | **3** | 市场平滑窗口 |
| `rotation_rank_min` | 45 | **30** | 旋转最小排名 |
| `rotation_rank_max` | 75 | **70** | 旋转最大排名 |
| `rotation_was_top_window` | 30 | **60** | 旋转顶部窗口 |

### 新增百分比排名字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `sell_rank_pct` | float | **0.15** | 卖出排名百分比（取代 `sell_rank_n`） |
| `rotation_bottom_pct` | float | **0.60** | 旋转底部百分比（取代 `rotation_bottom_threshold`） |
| `rotation_rank_min_pct` | float | **0.30** | 旋转买入最小百分比 |
| `rotation_rank_max_pct` | float | **0.70** | 旋转买入最大百分比 |
| `rotation_was_top_pct` | float | **0.15** | 旋转顶部百分比（取代 `rotation_was_top_n`） |
| `top_n_retention_pct` | float | **0.20** | 留存率百分比（取代 `top_n_retention`） |

计算方式（使用处做转换）：

```python
total = len(scored_stocks)
sell_rank_count = int(total * sell_rank_pct)
rotation_bottom_rank = int(total * rotation_bottom_pct)
rotation_min_rank = int(total * rotation_rank_min_pct)
rotation_max_rank = int(total * rotation_rank_max_pct)
rotation_was_top_count = int(total * rotation_was_top_pct)
top_n_retention_count = int(total * top_n_retention_pct)
```

### 删除的旧字段

`sell_rank_n`、`rotation_bottom_threshold`、`rotation_was_top_n`、`top_n_retention` 不再使用。

## 三、前端同步

### 默认值（`StrategyConfigView.vue` 中 `form`）

根据 DB 值同步更新所有默认值，新增缺失字段。

### 新增表单字段

模板中补充 `use_momentum_penalty`、`use_trend_penalty`、`use_score_decline_filter` 的开关组件。

### 表单展示字段（`compareFields`）

新增百分比字段的展示。

## 四、改动范围

| 文件 | 改动 |
|------|------|
| `dao/strategy_config.py` | 更新默认值，新增百分比字段，删除旧字段 |
| `execution/scoring.py` | 移除 `if self._strategy_config`，改用百分比 |
| `execution/backtest_pipeline.py` | 移除 `getattr` 兜底 |
| `execution/market_regime.py` | 移除 `getattr` 兜底，改用百分比 |
| `execution/suggestion_pipeline.py` | 移除 `if self.strategy_config and` |
| `strategy/multi_stock_strategy.py` | 百分比计算转换，清理 `top_ts_codes` 死参 |
| `frontend/.../StrategyConfigView.vue` | 更新默认值、新增表单字段 |
