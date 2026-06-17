# Implementation Plan: Cumulative Risk + Median Removal

## Overview

Two independent but merge-friendly changes to the market phase system:

1. **Cumulative Risk Scaling** — Add bear-market scaling to `_compute_phase_multipliers()` so that deep cumulative drawdowns tighten crash/decline thresholds. Bull-market protection (already implemented) is preserved.

2. **Remove Median Content** — `ranking_median`, `ranking_median_smoothed`, and `ranking_regime` (3-state trending_up/sideways/trending_down) are used neither for decisions nor for reliable analysis. Remove them from storage, API, and frontend. Keep `ranking_high_pct`, `ranking_low_pct` (valid breadth indicators).

## Task List

### Layer 1: Backend Core — scoring.py

#### Task 1: Remove median state from ScoreManager
- Remove `self._ranking_median_buffer: List[float] = []` from `__init__`
- In `compute_market_regime()`:
  - Keep `rank_scores` and `rank_scores_sorted` (still needed for high_pct/low_pct)
  - Remove `ranking_median = float(rank_scores_sorted[n // 2])`
  - Remove `self._ranking_median_buffer.append(ranking_median)`
  - Remove `ranking_median_smoothed = smooth_market_indicator(...)`
  - Remove 3-state regime classification block
- In `_last_market_data` dict:
  - Remove `"ranking_median"`, `"ranking_median_smoothed"`, `"ranking_regime"`

#### Task 2: Add cumulative risk scaling to `_compute_phase_multipliers()`
- Change `scale` computation from one-direction to two-direction:

  ```python
  # BEFORE
  if cum > 0:
      scale = min(3.0, 1.0 + cum * 5)
  else:
      scale = 1.0

  # AFTER
  if cum > 0:
      scale = min(3.0, 1.0 + cum * 5)       # bull: lenient
  elif cum < -0.05:
      scale = max(0.5, 1.0 + cum * 2)        # bear: strict
  else:
      scale = 1.0
  ```

- Key parameters:
  - Bull cap: 3.0x (same as before, prevents over-leniency)
  - Bear floor: 0.5x (crash_th = -6% * 0.5 = -3% at deepest)
  - Bear scaling rate: 2x per unit of cum (at cum=-0.25: scale=0.5)
  - Dead zone: cum ∈ [-0.05, 0] → scale=1.0 (small fluctuations ignored)

### Layer 2: DAO / Schema

#### Task 3: `dao/execution_daily_snapshot.py`
- Remove: `ranking_median: float = 0.0`
- Remove: `ranking_regime: str = ""`

#### Task 4: `schemas.py` — MarketDataEmbed
- Remove: `ranking_median: float = 0.0`
- Remove: `ranking_median_smoothed: float = 0.0`
- Remove: `ranking_regime: str = ""`
- Keep: `ranking_high_pct`, `ranking_low_pct`

### Layer 3: Backend API

#### Task 5: `execution/backtest_service.py`
- `get_daily_snapshots()` response: remove `"ranking_median"`, `"ranking_regime"`

### Layer 4: Frontend

#### Task 6: `src/api/backtestRecord.ts` — DailySnapshot interface
- Remove: `ranking_median: number`
- Remove: `ranking_regime: string`

#### Task 7: `src/components/OverviewChart.vue`
- OverviewChartItem interface: remove `ranking_median`, `ranking_regime`
- Template: remove `rankingRegime` tooltip block
- Chart: remove "排序分中位数" series, remove corresponding Y-axis
- Legend: remove "排序分中位数", "急跌阈值" (threshold was referencing ranking axis)
- Y-axis: remove `id: 'ranking'` axis (no longer needed)

#### Task 8: `src/views/BacktestRecordsView.vue`
- `loadMarketData()`: remove `ranking_median`, `ranking_regime` mapping

### Layer 5: Analysis Scripts (non-breaking)

#### Task 9: Update analysis scripts
- `analyze_regime.py` — references `ranking_median`, `ranking_smoothed` from snapshots. Remove or isolate to historical fallback.
- `analyze_phase_strategy.py` — same treatment

### Layer 6: Docs

#### Task 10: Update docs
- `docs/superpowers/specs/2026-06-16-market-phase-strategy.md` — add cumulative risk section
- `docs/superpowers/specs/2026-06-16-market-indicators-design.md` — note median fields removed
- `docs/features-indicators.md` — update field table

## Execution Order

```
Task 1  (scoring.py: remove median)      ─┐ Core logic first
Task 2  (scoring.py: cumulative risk)     ─┤
                                          │
Task 3  (dao/execution_daily_snapshot.py) ─┐ DAO second
Task 4  (schemas.py)                      ─┘
                                          │
Task 5  (backtest_service.py)            ─┤ API third
                                          │
Task 6-8 (frontend)                       ─┤ Frontend fourth
                                          │
Task 9  (analysis scripts)               ─┘ Optional/fifth
Task 10 (docs)                            ─┤ Docs sixth
```

## Verification

1. After Task 1-2: Import check — `python -c "from trade_alpha.execution.scoring import ScoreManager"`
2. After Task 3-4: Import check — modules load without errors
3. After Task 5: Backend starts — `curl http://localhost:8000/api/backtests/`
4. After Task 6-8: Frontend renders chart without error (check browser console)
5. Full integration: Run backtest, verify phases still trigger correctly
