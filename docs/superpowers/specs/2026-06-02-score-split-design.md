# Score Split — Ranking Score & Composite Score

## Motivation

Currently a single score (`r["score"]`) is used for both ranking and buy/sell threshold
decisions. The score is EWMA-smoothed in `_smooth_scores` for stability, but this also
dampens the buy/sell signals — making it harder to react quickly to score drops.

The fix: split the score into two separate values with different purposes.

## Design

### Score Flow

```
Before:
compute_scores → raw score → EWMA → same score for ranking + threshold

After:
compute_scores → raw score → +trend_bonus +vol_penalty +momentum_boost
                              ↓
                         composite_score ──→ buy/sell threshold
                              ↓
                         EWMA smoothing ──→ ranking_score → ranking
```

### Score Definitions

| Score | Formula | Purpose |
|-------|---------|---------|
| `score` (raw) | `compute_scores()` output | Baseline probability score |
| `composite_score` | `score + trend_bonus + vol_penalty + momentum_boost` | Buy/sell threshold decisions |
| `ranking_score` | EWMA `composite_score` | Ranking only |

### New Config Fields

| Field | Type | Default | Tab Placement |
|-------|------|---------|---------------|
| `ranking_smooth_window` | int | 3 | 排名优化 |
| `ranking_smooth_alpha` | float | 0.5 | 排名优化 |

### Pipeline Changes

**`_smooth_scores` refactored:**
- Removed: modifying `r["score"]` directly
- Added: writing to `r["ranking_score"]`
- alpha is read from strategy config, not hardcoded at 0.5
- window used to compute: `alpha = 2 / (window + 1)`

**`_predict` flow change:**
1. `compute_scores` → raw score into `r["score"]`
2. `_apply_trend_bonus` → stores in `r["trend_bonus"]`
3. `_apply_volatility_penalty` → stores in `r["vol_penalty"]`
4. `_apply_momentum_boost` → stores in `r["momentum_bonus"]`

After all bonuses (before creating ScoredStock):
```python
for r in pred_results.values():
    r["composite_score"] = r["score"] + r.get("trend_bonus", 0) + r.get("vol_penalty", 0) + r.get("momentum_bonus", 0)

self._smooth_scores(pred_results)
```

5. `_smooth_scores` → reads `r["composite_score"]`, writes `r["ranking_score"]`

**ScoredStock.score** is now fed from `composite_score`:
```python
score=r.get("composite_score", r["score"]),
```

**`_record_ranks`** sorted by `ranking_score`:
```python
scored.sort(key=lambda s: getattr(s, 'ranking_score', s.score), reverse=True)
```

**`_apply_momentum_boost`** base score reference:
- Already checks `r.get("composite_score") or r.get("score", 0)` — works as-is

### Frontend Changes

**StrategyConfigView.vue — 排名优化 tab:**
Add after 动量加权:
- `ranking_smooth_window` (number input, 3 default)
- `ranking_smooth_alpha` (number input, 0.01 step, 0.5 default)

**PredictionChart.vue:**
Add new line series for "排名分":
- Name: `排名分`
- Field: `ranking_score` from pred_results
- Color: blue (#2196F3)
- Legend starts: visible by default
- Tooltip: show all three scores

**BacktestRecordsView.vue — config dialog:**
Add the two new fields to the strategy config display.

### Affected Files

| Layer | File | Change |
|-------|------|--------|
| Backend Model | `dao/strategy_config.py` | Add `ranking_smooth_window`, `ranking_smooth_alpha` |
| Backend Snapshot | `dao/execution.py:StrategySnapshotEmbed` | Add same 2 fields |
| Backend Pipeline | `execution/pipeline.py` | Refactor `_smooth_scores`, `_predict`, `_record_ranks` |
| Frontend Type | `api/strategyConfig.ts` | Add 2 fields to Strategy |
| Frontend Edit | `views/StrategyConfigView.vue` | Add fields to 排名优化 tab |
| Frontend Chart | `components/PredictionChart.vue` | Add 排名分 line series |
| Frontend Dialog | `views/BacktestRecordsView.vue` | Show new fields in config