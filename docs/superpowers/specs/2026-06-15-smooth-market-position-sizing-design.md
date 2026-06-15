# Smooth Market Position Sizing Design

**Date**: 2026-06-15  
**Status**: Draft  
**Supercedes**: The position scaling aspect of `2026-06-14-market-aware-trading-design.md`

## Problem

The current market-aware position sizing uses **raw daily `ranking_median`** to compute `score_scalar`, which gates the `max_position_pct` for new buys. This has two shortcomings:

1. **Raw median is noisy** — day-to-day fluctuations cause position caps to jump
2. **No recovery detection** — once median turns negative, the scalar immediately drops regardless of whether the market is already improving

Analysis of `live_long` strategy showed that a single missed mega-winner (工业富联, +$382K) was sufficient to flip the net benefit negative, because aggressive position shrinkage on weak days caused the stock to be skipped entirely.

## Solution: Smooth + Recovery-Aware

Introduce **EMA smoothing** on `ranking_median` and a **recovery gate** that skips position scaling when the market is improving.

### Component 1: `smooth_median()` in `scoring.py`

Pure function stateless EWMA smoother:

```python
def smooth_median(
    raw_median: float,
    prev_smoothed: Optional[float],
    alpha: float = 0.3,
) -> float:
```

- Input: today's raw median, yesterday's smoothed, smoothing factor
- Output: today's smoothed median
- First call (prev_smoothed is None): returns raw_median directly
- Subsequent: `alpha * raw + (1 - alpha) * prev`

The cancelling `alpha` reuses the existing `ranking_smooth_alpha` from `StrategyConfig` (default 0.3).

### Component 2: `PositionManager` State (`base.py`)

One new optional attribute:

```python
self.ranking_median_smoothed: Optional[float] = None
```

Set by the pipeline each day, read by `_market_score_scalar()`.

### Component 3: Pipeline Integration (`backtest_pipeline.py`)

After computing `ranking_median` in `_compute_market_regime()`:

```python
from trade_alpha.execution.scoring import smooth_median

ranking_median_raw = float(rank_scores_sorted[n // 2])
ranking_median_smoothed = smooth_median(
    ranking_median_raw,
    self.strategy.ranking_median_smoothed,
    alpha=self.strategy_config.ranking_smooth_alpha,
)
self.strategy.ranking_median = ranking_median_raw
self.strategy.ranking_median_smoothed = ranking_median_smoothed
```

### Component 4: New `_market_score_scalar()` Logic (`multi_stock_strategy.py`)

Three-tier decision:

```
smoothed >= 0?              → scalar = 1.0 (market strong, no cap)
smoothed < 0 but raw > smoothed? → scalar = 1.0 (recovering, no cap)
smoothed < 0 and raw <= smoothed? → scalar = max(0.30, 1.0 + smoothed * 5)
```

Implementation:

```python
def _market_score_scalar(self) -> float:
    if not self.use_market_aware_trading or self.ranking_median_smoothed is None:
        return 1.0
    # Strong market → no cap
    if self.ranking_median_smoothed >= 0:
        return 1.0
    # Recovering market → no cap
    if self.ranking_median is not None and self.ranking_median > self.ranking_median_smoothed:
        return 1.0
    # Still deteriorating → cap with smoothed median
    scalar = max(0.30, 1.0 + self.ranking_median_smoothed * 5)
    return scalar
```

### Data Flow

```
BacktestPipeline (daily loop)
│
├─ _compute_market_regime(pred_results)
│   ├─ ranking_median_raw = median of all ranking_scores
│   ├─ regime = classify(ranking_median_raw)
│   └─ ranking_median_smoothed = smooth_median(ranking_median_raw, prev)
│
├─ strategy.ranking_median = ranking_median_raw
├─ strategy.ranking_median_smoothed = ranking_median_smoothed
│
├─ _save_snapshot(...)  ← stores ranking_median (raw) + score_scalar (from smoothed)
│
└─ make_decisions(...)
    └─ _market_score_scalar()
```

### Behavior Comparison

| Scenario | Before (raw) | After (smoothed + recovery) |
|----------|-------------|---------------------------|
| Strong market (median > 0) | scalar=1.0 | scalar=1.0 (=) |
| Sudden crash day 1 | scalar drops sharply | scalar stays high (lag) |
| Gradual recovery from weak | scalar stays low until median>0 | scalar recovers once raw>smoothed |
| False-positive single bad day | scalar drops, recovers next day | scalar mostly unchanged |

### Parameter

- `ranking_smooth_alpha` — already exists in `StrategyConfig`, default 0.3
  - Higher = smoother (less responsive to daily noise)
  - Lower = more responsive (reacts faster to regime changes)

### What Does NOT Change

- `ranking_median` stored in daily snapshots remains raw value for transparency
- Regime classification (`trending_up` / `sideways` / `trending_down`) remains based on raw median
- `score_scalar` in daily snapshots is computed from smoothed median
- `max_position_pct` in `PortfolioManager` is unchanged — only the scalar passed to `reserve_funds` changes
- Suggestion pipeline (`suggestion_pipeline.py`) mirrors the same integration