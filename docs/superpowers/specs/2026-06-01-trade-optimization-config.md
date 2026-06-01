# Trade Optimization Tab — Strategy Config

## Motivation

Currently the "排名优化" tab in StrategyConfig mixes score-ranking features (momentum,
trend, volatility) with the explosion filter, and there is no mechanism to handle
over-positioning or price-acceleration risks. A dedicated "交易优化" tab consolidates
all trade-level guardrails.

## Design

### Tab Structure Change

```
Before:  基本配置 | 多股票配置 | 排名优化
After:   基本配置 | 多股票配置 | 排名优化 | 交易优化
```

### New Field Definitions

**满仓容忍度** — Forced sell when portfolio is over-positioned too long

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `use_full_position_sell` | bool | false | Enable |
| `full_position_threshold` | float | 0.90 | Total value threshold (90%) |
| `full_position_days` | int | 3 | Consecutive days above threshold |
| `full_position_score_window` | int | 5 | Window for avg score calculation |
| `full_position_sell_count` | int | 1 | Number of stocks to sell per trigger |

**加速排除** — Block buy when price is accelerating

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `use_acceleration_filter` | bool | false | Enable |
| `acceleration_window` | int | 5 | Detection window (days) |
| `acceleration_cum_return` | float | 0.15 | Cumulative return threshold (>15%) |
| `acceleration_up_ratio` | float | 0.80 | Up-day ratio threshold (>80%) |

**暴涨排除** (moved from 排名优化 tab)

Unchanged. Fields: `use_explosion_filter`, `explosion_price_threshold`, `explosion_volume_ratio`, `explosion_window`.

### Backend — Pipeline Logic

**满仓容忍度** (`_apply_full_position_sell` in pipeline, after `_record_ranks`):
```
if total_value / initial_capital >= threshold for N consecutive days:
    for each stock in positions:
        compute avg score over score_window
    find stock with lowest avg score
    issue sell order for that stock (reason: "full_position_forced_sell")
```

**加速排除** (`_apply_acceleration_filter` in pipeline, alongside `_filter_explosions`):
```
for each candidate buy stock:
    close_prices = peek_history_data(ts_code, acceleration_window)
    cum_return = (close[-1] - close[0]) / close[0]
    up_days = count of days where close[i] > close[i-1]
    up_ratio = up_days / (acceleration_window - 1)
    if cum_return > acceleration_cum_return AND up_ratio > acceleration_up_ratio:
        exclude this stock
        record: is_acceleration_excluded=true, accel_cum_return, accel_up_ratio
```

### Recording & Display

**加速排除** — Same pattern as 暴涨排除:
- Record in daily snapshot `predictions[ts_code]`: `is_acceleration_excluded`, `accel_cum_return`, `accel_up_ratio`
- New aggregated endpoint: `GET /{result_id}/acceleration-excluded`
- Display in 结果弹窗 overview tab (alongside 暴涨排除)

**满仓容忍度**:
- Record in `execution_trade`: `reason = "full_position_forced_sell"`
- Record in daily snapshot `predictions[ts_code]`: `is_forced_sell=true`, `forced_sell_reason="full_position"`
- New aggregated endpoint: `GET /{result_id}/forced-sell-stocks`
- Display in overview tab

### Overview Tab in Result Dialog

Current: `概览 | 盈亏分析 | 暴涨排除`

Changed to: `概览 | 盈亏分析 | 交易优化`

The "交易优化" tab contains 3 sub-sections stacked vertically:
- **暴涨排除记录** (existing, moved from its own tab)
- **加速排除记录** (new)
- **满仓强制卖出** (new)

### Affected Files

| Layer | File | Change |
|-------|------|--------|
| Backend Model | `dao/strategy_config.py` | Add 10 new fields |
| Backend Snapshot | `dao/execution.py:StrategySnapshotEmbed` | Add same 10 fields |
| Backend Pipeline | `execution/pipeline.py` | `_apply_full_position_sell`, `_apply_acceleration_filter` |
| Backend API | `api/routers/backtest_records.py` | New endpoints: `/acceleration-excluded`, `/forced-sell-stocks` |
| Frontend Type | `api/strategyConfig.ts` | Add 10 new fields to `Strategy` |
| Frontend Edit | `views/StrategyConfigView.vue` | New "交易优化" tab, move explosion filter here |
| Frontend Display | `views/BacktestRecordsView.vue` | Show new fields in config dialog; new overview sub-sections |