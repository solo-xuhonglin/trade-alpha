# ScoreManager Refactoring Design

**Date**: 2026-06-15
**Status**: Draft

## Problem

Score-related logic is scattered across `backtest_pipeline.py` (761 lines) and `suggestion_pipeline.py` (516 lines), with significant duplication:

1. `_predict()` is nearly identical in both pipelines (~90 lines each) — the full scoring pipeline from raw predictions to ranked ScoredStock objects
2. `_record_ranks()` is duplicated verbatim
3. `_apply_full_position_sell()` is duplicated with minor differences
4. `_calc_linear_slope()` and `_calc_r_squared()` are duplicated in `backtest_pipeline.py` (already exist in `scoring.py`)
5. `_apply_acceleration_filter()` exists only in `backtest_pipeline.py` but belongs with scoring logic
6. `composite_score` formula is inline in `_predict()` rather than centralized
7. `ScoredStockHistoryHelper` is a separate class for cross-day rank tracking but its lifecycle is tightly coupled to the scoring pipeline

## Solution: ScoreManager Class

Introduce a stateful `ScoreManager` class in `execution/scoring.py` that owns all cross-day scoring state and orchestrates the full scoring lifecycle. Both pipelines use it via composition (has-a).

### Class Definition

```python
class ScoreManager:
    """Stateful score lifecycle manager.

    Owns cross-day state (score buffer, smoothed median, rank history)
    and orchestrates the full scoring pipeline from raw predictions
    to ranked ScoredStock objects and market regime.
    """

    def __init__(
        self,
        strategy_config: StrategyConfig,
        model_config: ModelConfig,
    ):
        self._strategy_config = strategy_config
        self._model_config = model_config
        self._score_buffer: Dict[str, List[float]] = {}
        self._rank_history: Dict[str, List[ScoredStock]] = {}
        self._rank_history_max: int = 60
        self._prev_ranking_median_smoothed: Optional[float] = None
        self._last_market_data: Optional[dict] = None
```

### Public API

#### `predict_and_score()`

```python
async def predict_and_score(
    self,
    predictor,
    data_loader: DataLoader,
    date: str,
    close_prices: Dict[str, float],
    name_map: Dict[str, str],
    start_date: str,
    vol_prices: Optional[Dict[str, float]] = None,
) -> Tuple[List[ScoredStock], Dict[str, Dict]]:
```

Full scoring pipeline:

1. Call `predictor.predict_batch()` → raw probabilities
2. Call `compute_scores()` → raw score per stock
3. Compute lookback window from strategy config
4. Load history data via `data_loader.peek_history_data()`
5. Apply `apply_trend_bonus`, `apply_trend_penalty`, `apply_volatility_penalty`
6. Apply `apply_momentum_boost`, `apply_momentum_penalty`
7. Apply `filter_explosions`
8. Apply `_apply_acceleration_filter` (moved from pipeline)
9. Compute `composite_score` = score + trend_bonus - trend_penalty - vol_penalty + momentum_bonus - momentum_penalty
10. Apply `smooth_scores`
11. Build `ScoredStock` objects
12. Call `_record_ranks` (moved from pipeline)
13. Call `_record_rank_history` (absorbed from ScoredStockHistoryHelper)
14. Compute `rank_improvement` (absorbed from ScoredStockHistoryHelper)
15. Return `(scored, pred_results)`

#### `compute_market_regime()`

```python
def compute_market_regime(self, pred_results: Dict[str, Dict]) -> str:
```

Moved from `backtest_pipeline._compute_market_regime()`:

1. Extract ranking_scores from pred_results
2. Compute ranking_median
3. Classify regime (trending_up / sideways / trending_down)
4. Compute ranking_high_pct / ranking_low_pct
5. Apply `smooth_median` → ranking_median_smoothed
6. Compute score_scalar
7. Update `_last_market_data` and `_prev_ranking_median_smoothed`
8. Return regime string

#### `get_score_buffer()`

```python
def get_score_buffer(self, ts_code: str) -> List[float]:
```

Returns the score buffer for a stock. Used by `_apply_full_position_sell()` in both pipelines to compute average score over a window.

#### `last_market_data` property

```python
@property
def last_market_data(self) -> Optional[dict]:
```

Returns the latest market data dict containing `ranking_median`, `ranking_median_smoothed`, `ranking_high_pct`, `ranking_low_pct`, `ranking_regime`, `score_scalar`.

### Absorbed from ScoredStockHistoryHelper

The `ScoredStockHistoryHelper` class from `execution/rank_tracker.py` is merged into `ScoreManager`:

- `_rank_history: Dict[str, List[ScoredStock]]` replaces `ScoredStockHistoryHelper._history`
- `_rank_history_max: int` replaces `ScoredStockHistoryHelper._max_entries`
- `_record_rank_history()` replaces `ScoredStockHistoryHelper.record_day()`
- `_compute_rank_improvement()` replaces `ScoredStockHistoryHelper.compute_rank_improvement()`

After this change, `execution/rank_tracker.py` is deleted.

### Private Methods (moved from pipelines)

- `_record_ranks(scored, pred_results)` — from both pipelines
- `_apply_acceleration_filter(pred_results, close_prices_hist)` — from backtest_pipeline
- `_record_rank_history(date, scored)` — from ScoredStockHistoryHelper.record_day
- `_compute_rank_improvement(ts_code, current_rank, window)` — from ScoredStockHistoryHelper.compute_rank_improvement

### Pipeline Changes

#### `backtest_pipeline.py`

- **Add**: `self.score_manager = ScoreManager(strategy_config, model_config)` in `__init__`
- **Delete**: `_predict()` method → replaced by `self.score_manager.predict_and_score()`
- **Delete**: `_compute_market_regime()` method → replaced by `self.score_manager.compute_market_regime()`
- **Delete**: `_record_ranks()` method → moved into ScoreManager
- **Delete**: `_apply_acceleration_filter()` method → moved into ScoreManager
- **Delete**: `_calc_linear_slope()` and `_calc_r_squared()` → already in scoring.py
- **Delete**: `self._score_buffer` → managed by ScoreManager
- **Delete**: `self._stock_helper` → absorbed by ScoreManager
- **Delete**: `self._prev_ranking_median_smoothed` → managed by ScoreManager
- **Delete**: `self._last_market_data` → managed by ScoreManager
- **Modify**: `_apply_full_position_sell()` uses `self.score_manager.get_score_buffer()`
- **Modify**: `_run_daily_loop()` reads market data from `self.score_manager.last_market_data`

#### `suggestion_pipeline.py`

- **Add**: `self.score_manager = ScoreManager(strategy_config, model_config)` in `__init__`
- **Delete**: `_predict()` method → replaced by `self.score_manager.predict_and_score()`
- **Delete**: `_record_ranks()` method → moved into ScoreManager
- **Delete**: `self._score_buffer` → managed by ScoreManager
- **Delete**: `self._stock_helper` → absorbed by ScoreManager
- **Modify**: `_apply_full_position_sell()` uses `self.score_manager.get_score_buffer()`

#### `execution/rank_tracker.py`

- **Delete**: Entire file. Functionality absorbed into ScoreManager.

### What Does NOT Change

- `PortfolioManager` — position management unchanged
- `MultiStockStrategy` — strategy decisions unchanged
- `compute_scores()` in `models/base.py` — raw score computation unchanged
- `ScoredStock` / `PendingOrder` in `schemas.py` — data structures unchanged
- Pure functions in `scoring.py` — retained and called by ScoreManager internally
- `_apply_full_position_sell()` — stays in pipelines but uses `score_manager.get_score_buffer()`

### Line Count Impact

| File | Change |
|------|--------|
| `execution/scoring.py` | +170 (ScoreManager class) |
| `execution/backtest_pipeline.py` | -130 (deleted methods + state) |
| `execution/suggestion_pipeline.py` | -100 (deleted methods + state) |
| `execution/rank_tracker.py` | -60 (deleted, absorbed) |
| **Net** | ~-120 lines |

### Data Flow (After Refactoring)

```
BacktestPipeline / SuggestionPipeline (daily loop)
│
├─ score_manager.predict_and_score(predictor, data_loader, ...)
│   ├─ predictor.predict_batch() → raw probs
│   ├─ compute_scores() → raw score
│   ├─ apply_trend_bonus/penalty, apply_volatility_penalty
│   ├─ apply_momentum_boost/penalty
│   ├─ filter_explosions
│   ├─ _apply_acceleration_filter
│   ├─ composite_score = score + bonuses - penalties
│   ├─ smooth_scores
│   ├─ _record_ranks
│   ├─ _record_rank_history + _compute_rank_improvement
│   └─ returns (scored, pred_results)
│
├─ score_manager.compute_market_regime(pred_results)
│   ├─ ranking_median, regime classification
│   ├─ smooth_median → ranking_median_smoothed
│   └─ score_scalar
│
├─ _apply_full_position_sell(...)
│   └─ score_manager.get_score_buffer(ts_code)
│
└─ strategy.make_decisions(scored, portfolio, ...)
```
