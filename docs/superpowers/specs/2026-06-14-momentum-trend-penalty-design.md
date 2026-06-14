# Momentum & Trend Penalty Design

## Summary

Add two independent toggle switches for **downside penalty** next to the existing momentum boost and trend bonus toggles. Bonus and penalty share the same calculation parameters. UI displays the combined net score (bonus - penalty) with a +/- sign.

## Background

Currently the ranking optimization section has:

| Feature | Toggle | Direction |
|---------|--------|-----------|
| 动量加权 | `use_momentum_boost` | only boost (up-day ratio) |
| 趋势加分 | `use_trend_bonus` | only bonus (slope > 0) |
| 波动扣分 | `use_volatility_penalty` | only penalty (volatility) |

This adds downside penalty capability: stocks with many down-days or negative slope should be penalized, using the same calculation parameters.

## Fields

### DAO — StrategyConfig

New fields on [strategy_config.py](../../backend/src/trade_alpha/dao/strategy_config.py):

| Field | Type | Default | Note |
|-------|------|---------|------|
| `use_momentum_penalty` | `bool` | `False` | after `max_momentum_bonus` |
| `use_trend_penalty` | `bool` | `False` | after `trend_max_bonus` |

**No new numeric parameters.** Both penalty types reuse existing params:
- momentum penalty: `momentum_window`, `max_momentum_bonus`
- trend penalty: `trend_bonus_window`, `trend_bonus_scale`, `trend_r2_threshold`, `trend_max_bonus`

### API Schema

[schemas.py](../../backend/src/trade_alpha/api/schemas.py):

- `StrategyCreateRequest`: add `use_momentum_penalty: Optional[bool] = False`, `use_trend_penalty: Optional[bool] = False`
- `StrategyUpdateRequest`: add `use_momentum_penalty: Optional[bool] = None`, `use_trend_penalty: Optional[bool] = None`

### Service

[strategy/service.py](../../backend/src/trade_alpha/strategy/service.py):

- `create_strategy()`: add params `use_momentum_penalty`, `use_trend_penalty` — auto-included via kwargs
- `update_strategy()`: add corresponding conditional assignment blocks

### Router

[strategy_config.py](../../backend/src/trade_alpha/api/routers/strategy_config.py):

- `create_strategy_endpoint()`: pass `request.use_momentum_penalty`, `request.use_trend_penalty`
- `update_strategy_endpoint()`: same

## Scoring Logic

### momentum_adjust (extend `apply_momentum_boost` in scoring.py)

```python
# Bonus (existing)
if strategy_config.use_momentum_boost:
    r["momentum_bonus"] = up_ratio * max_bonus
else:
    r["momentum_bonus"] = 0.0

# Penalty (new)
if strategy_config.use_momentum_penalty:
    down_ratio = 1 - up_ratio
    r["momentum_penalty"] = down_ratio * max_bonus
else:
    r["momentum_penalty"] = 0.0
```

### trend_adjust (extend `apply_trend_bonus` in scoring.py)

```python
# Bonus (existing)
if slope > 0 and r_squared >= r2_threshold:
    r["trend_bonus"] = min(max_bonus, slope * r_squared * scale)
else:
    r["trend_bonus"] = 0.0

# Penalty (new)
if strategy_config.use_trend_penalty:
    if slope < 0 and r_squared >= r2_threshold:
        r["trend_penalty"] = min(max_bonus, abs(slope) * r_squared * scale)
    else:
        r["trend_penalty"] = 0.0
else:
    r["trend_penalty"] = 0.0
```

## Composite Score Formula

Updated in both [suggestion_pipeline.py](../../backend/src/trade_alpha/execution/suggestion_pipeline.py) and [backtest_pipeline.py](../../backend/src/trade_alpha/execution/backtest_pipeline.py):

```python
composite_score = score
                + r.get("trend_bonus", 0) - r.get("trend_penalty", 0)
                - r.get("vol_penalty", 0)
                + r.get("momentum_bonus", 0) - r.get("momentum_penalty", 0)
```

## Data Models — new float fields

Add `momentum_penalty` and `trend_penalty` (float, default 0.0) to:

| Model | Location |
|-------|----------|
| `ScoredStock` | [backtest_pipeline.py](../../backend/src/trade_alpha/execution/backtest_pipeline.py) |
| `ExecutionDailySnapshot` | [dao/execution.py](../../backend/src/trade_alpha/dao/execution.py) |
| `LiveDailyStockScore` | [dao/live_daily_stock_score.py](../../backend/src/trade_alpha/dao/live_daily_stock_score.py) |
| `LiveOrderSuggestion` | [dao/live_order_suggestion.py](../../backend/src/trade_alpha/dao/live_order_suggestion.py) |
| `OrderSuggestion` | [dao/order_suggestion.py](../../backend/src/trade_alpha/dao/order_suggestion.py) |

## Suggestion/Backtest Service Serialization

Add `momentum_penalty` and `trend_penalty` fields in:
- [suggestion_service.py](../../backend/src/trade_alpha/execution/suggestion_service.py) — `list_stock_daily_scores` response
- [backtest_service.py](../../backend/src/trade_alpha/execution/backtest_service.py) — snapshot serialization

## Frontend

### StrategyConfigView.vue — Form & UI

Layout for each group — one row with two switches, shared params below:

```
[momentum_boost v-switch 动量加权]     [momentum_penalty v-switch 动量扣分]
窗口天数 [___12___]    最大动量加成 [__0.15__]

[trend_bonus v-switch 趋势加分]         [trend_penalty v-switch 趋势扣分]
窗口天数 [___15___]   斜率系数 [__0.03__]
R² 阈值  [__0.30__]   最大加分  [__0.10__]
```

- Params `disabled` condition: `!form.use_momentum_boost && !form.use_momentum_penalty` (both off → disabled)
- `openDialog` copy: add `use_momentum_penalty`, `use_trend_penalty`
- `saveStrategy` create/update: add both fields
- `form` defaults: both `false`

### StrategyChips.vue — Strategy display chips

Add two new chips:

```
趋势扣分 [chip: 启用/关闭]
动量扣分 [chip: 启用/关闭]
```

### Score Display — net combined with sign

In all places where bonus/penalty breakdown is shown, **merge bonus and penalty into a single net line** with +/- sign:

| Line | Calculation | Color |
|------|-------------|-------|
| 趋势: +X / -X | `trend_bonus - trend_penalty` > 0 ? + : - | green / red |
| 波动扣分: -X | `vol_penalty` (unchanged) | red |
| 动量: +X / -X | `momentum_bonus - momentum_penalty` > 0 ? + : - | green / red |

Affected locations:

| File | What changes |
|------|-------------|
| [StockKlineChart.vue](../../frontend/src/components/StockKlineChart.vue) | tooltip bonusParts — merge trend/momentum lines |
| [LivePredictionChart.vue](../../frontend/src/components/LivePredictionChart.vue) | computed props — merge into net values |
| [LiveDailySuggestionsView.vue](../../frontend/src/views/LiveDailySuggestionsView.vue) | composite score breakdown — merge |
| [DailyRankingsView.vue](../../frontend/src/views/DailyRankingsView.vue) | composite score breakdown — merge |
| [BacktestRecordsView.vue](../../frontend/src/views/BacktestRecordsView.vue) | strategy config detail — add penalty toggle status |

### BacktestRecordsView.vue — compare fields

Add to the compare field list:
- `use_momentum_penalty` / `use_trend_penalty`

### API types

[strategyConfig.ts](../../frontend/src/api/strategyConfig.ts): `Strategy` interface add `use_momentum_penalty`, `use_trend_penalty`

## Mutex Rule

Bonus and penalty can be **independently enabled/disabled**. When both are on:
- Net effect = bonus - penalty
- If net > 0 → positive (green), net < 0 → negative (red)
- When both off → both bonus and penalty are 0 (current behavior)
