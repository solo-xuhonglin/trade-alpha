# Market Regime Analyzer: Extract from ScoreManager

## 1. Background

The current `ScoreManager` in `execution/scoring.py` has grown too large, mixing two distinct responsibilities:

1. **Stock scoring** — model inference, score computation, trend/momentum bonuses, smoothing
2. **Market analysis** — phase detection (crash/decline/recovery/normal), retention rate, score-return correlation, baseline volatility

`compute_market_regime()` is the most overloaded method at ~80 lines, computing ranking statistics, market indicators, phase-based multipliers, and baseline volatility in a single function.

Additionally, `_rank_history` (per-stock daily rank tracking) lives in `ScoreManager` but is consumed by both `RotationMode` and the market indicators (retention rate, correlation), creating unnecessary coupling.

## 2. Design

Extract a new `MarketRegimeAnalyzer` class that owns all market analysis logic and `_rank_history` management, leaving `ScoreManager` focused purely on stock scoring.

### 2.1 New file: `backend/src/trade_alpha/execution/market_regime.py`

```python
class MarketRegimeAnalyzer:
    """Market regime analysis: phase detection, indicators, baseline volatility.

    Owns _rank_history and all market-level buffers.
    Receives daily data from the pipeline and stock_map from ScoreManager.
    """

    def __init__(self, strategy_config: StrategyConfig):
        self._strategy_config = strategy_config
        # --- Rank tracking (from ScoreManager) ---
        self._rank_history: Dict[str, List[ScoredStock]] = {}
        self._rank_history_max: int = ...
        # --- Market buffers ---
        self._low_pct_buffer: List[float] = []
        self._retention_rate_buffer: List[float] = []
        self._correlation_buffer: List[float] = []
        self._cum_values_buffer: List[float] = []  # for baseline vol computation
        self._current_phase: str = "flat"
        self._last_market_data: Optional[dict] = None
```

### 2.2 Responsibilities moved from ScoreManager → MarketRegimeAnalyzer

| Method/Field | From | To |
|---|---|---|
| `_rank_history` | ScoreManager | MarketRegimeAnalyzer |
| `_rank_history_max` | ScoreManager | MarketRegimeAnalyzer |
| `_record_ranks()` | ScoreManager | MarketRegimeAnalyzer |
| `_record_rank_history()` | ScoreManager | MarketRegimeAnalyzer |
| `_compute_rank_improvement()` | ScoreManager | MarketRegimeAnalyzer |
| `get_rank_history()` | ScoreManager | MarketRegimeAnalyzer |
| `_low_pct_buffer` | ScoreManager | MarketRegimeAnalyzer |
| `_retention_rate_buffer` | ScoreManager | MarketRegimeAnalyzer |
| `_correlation_buffer` | ScoreManager | MarketRegimeAnalyzer |
| `_rebalanced_cum_buffer` (renamed `_cum_values_buffer`) | ScoreManager | MarketRegimeAnalyzer |
| `_last_market_data` | ScoreManager | MarketRegimeAnalyzer |
| `_market_phase` (`_current_phase`) | ScoreManager | MarketRegimeAnalyzer |
| `compute_market_regime()` | ScoreManager | `analyze()` |
| `_compute_phase_multipliers()` | ScoreManager | MarketRegimeAnalyzer |
| `_compute_top_n_retention()` | ScoreManager | MarketRegimeAnalyzer |
| `_compute_score_return_correlation()` | ScoreManager | MarketRegimeAnalyzer |

### 2.3 `MarketRegimeAnalyzer.analyze()` interface

```python
def analyze(
    self,
    stock_map: Dict[str, ScoredStock],
    daily_rebalanced_values: List[float],
) -> str:
    """Compute market regime and return phase name.

    Args:
        stock_map: Today's scored stocks from ScoreManager.
        daily_rebalanced_values: Equal-weight daily-rebalanced index
            series from BaselineTracker.

    Returns:
        market_phase: "up" / "flat" / "down"
    """
```

Internally, `analyze()` performs:
1. Compute ranking stats (`ranking_high_pct`, `ranking_low_pct`)
2. Update `_low_pct_buffer`
3. Call `_compute_phase_multipliers()` — phase detection + multipliers
4. Compute retention rate + correlation (market indicators)
5. Compute baseline volatility multiplier
6. Store `_last_market_data` dict
7. Return phase name

### 2.4 60-day limit fix

In `_compute_phase_multipliers()`:

```python
# Before: hard limit at 60
trend_60d = 0.0
if len(daily_rebalanced_values) >= 61:
    trend_60d = (daily_rebalanced_values[-1] - daily_rebalanced_values[-61]) / daily_rebalanced_values[-61]

# After: use whatever data is available
trend_days = min(len(daily_rebalanced_values) - 1, 60)
if trend_days >= 1:
    trend_60d = (daily_rebalanced_values[-1] - daily_rebalanced_values[-1 - trend_days]) / daily_rebalanced_values[-1 - trend_days]
else:
    trend_60d = 0.0
```

Similarly for the 5-day check:

```python
# Before
if len(daily_rebalanced_values) < 6:
    return 1.0, 1.0, "flat"

# After
if len(daily_rebalanced_values) < 2:
    return 1.0, 1.0, "flat"
rebalanced_5d_lookback = min(5, len(daily_rebalanced_values) - 1)
```

### 2.5 `daily_rebalanced_cum` parameter removed

Current `compute_market_regime()` accepts both `daily_rebalanced_values` (list) and `daily_rebalanced_cum` (float). The cum value is redundant because the analyzer can compute cumulative returns from the values list internally.

### 2.6 Rank tracking flow

```
ScoreManager.predict_and_score()
  → scores computed, ScoredStock objects built
  → scored_list = list(stock_map.values())
  → market_analyzer.record_ranking_scores(scored_list, pred_results)
      → records ranks, updates _rank_history
  → market_analyzer.compute_rank_improvement(ts_code, rank, window) for each
      → writes to stock.rank_improvement
```

## 3. Pipeline integration

### 3.1 PipelineContext

```python
class PipelineContext:
    def __init__(self, ..., market_analyzer: MarketRegimeAnalyzer):
        self.market_analyzer = market_analyzer
```

### 3.2 BacktestPipeline

```diff
 # Initialization
+self.market_analyzer = MarketRegimeAnalyzer(strategy_config)
 self.score_manager = ScoreManager(strategy_config, model_config)
 self.ctx = PipelineContext(
     data_loader=..., portfolio=..., 
     score_manager=self.score_manager,
+    market_analyzer=self.market_analyzer,
     ...
 )

 # Warmup / Daily loop
-stock_map = await self.score_manager.predict_and_score(...)
+stock_map = await self.score_manager.predict_and_score(
+    ..., market_analyzer=self.market_analyzer,
+)

-self.score_manager.compute_market_regime(
-    stock_map,
-    daily_rebalanced_values=baseline_tracker.daily_rebalanced_values,
-    daily_rebalanced_cum=baseline_tracker.daily_rebalanced_cum,
-)
+self.market_analyzer.analyze(
+    stock_map,
+    daily_rebalanced_values=baseline_tracker.daily_rebalanced_values,
+)

-market_data = MarketDataEmbed(**self.score_manager.last_market_data)
+market_data = MarketDataEmbed(**self.market_analyzer.last_market_data)

 # Snapshot save
-snapshot.update({"$set": self.score_manager.last_market_data})
+snapshot.update({"$set": self.market_analyzer.last_market_data})
```

### 3.3 SuggestionPipeline

Same pattern as BacktestPipeline.

## 4. RotationMode change

```diff
 # rotation_mode.py
-rank_history = ctx.score_manager.get_rank_history(st.ts_code)
+rank_history = ctx.market_analyzer.get_rank_history(st.ts_code)
```

## 5. Variables removed from ScoreManager

| Variable | Reason |
|---|---|
| `_rank_history` | Moved to MarketRegimeAnalyzer |
| `_rank_history_max` | Moved to MarketRegimeAnalyzer |
| `_low_pct_buffer` | Moved to MarketRegimeAnalyzer |
| `_retention_rate_buffer` | Moved to MarketRegimeAnalyzer |
| `_correlation_buffer` | Moved to MarketRegimeAnalyzer |
| `_rebalanced_cum_buffer` | Moved to MarketRegimeAnalyzer |
| `_last_market_data` | Moved to MarketRegimeAnalyzer |
| `_market_phase` | Moved to MarketRegimeAnalyzer |

## 6. Methods removed from ScoreManager

| Method | Reason |
|---|---|
| `_record_ranks()` | Moved to MarketRegimeAnalyzer |
| `_record_rank_history()` | Moved to MarketRegimeAnalyzer |
| `_compute_rank_improvement()` | Moved to MarketRegimeAnalyzer |
| `get_rank_history()` | Moved to MarketRegimeAnalyzer |
| `compute_market_regime()` | Replaced by `MarketRegimeAnalyzer.analyze()` |
| `_compute_phase_multipliers()` | Moved to MarketRegimeAnalyzer |
| `_compute_top_n_retention()` | Moved to MarketRegimeAnalyzer |
| `_compute_score_return_correlation()` | Moved to MarketRegimeAnalyzer |

## 7. Files changed

| File | Change |
|---|---|
| `execution/market_regime.py` | **New** — `MarketRegimeAnalyzer` class |
| `execution/scoring.py` | **Remove** market/rank methods, keep pure scoring |
| `execution/context.py` | **Add** `market_analyzer` field to PipelineContext |
| `execution/backtest_pipeline.py` | Use `market_analyzer` instead of `score_manager` for market/rank |
| `execution/suggestion_pipeline.py` | Same |
| `strategy/modes/rotation_mode.py` | `ctx.market_analyzer.get_rank_history()` |
| `strategy/multi_stock_strategy.py` | No change |
| `strategy/modes/trend_mode.py` | No change |
| `schemas.py` | No change |
| `dao/strategy_config.py` | No change |
| `dao/execution.py` | No change |
| `dao/execution_daily_snapshot.py` | No change |

## 8. Backward compatibility

- `MarketDataEmbed` structure unchanged
- `ExecutionDailySnapshot` fields unchanged
- Old backtest records in MongoDB remain readable
- Frontend API unchanged
- No database migration needed