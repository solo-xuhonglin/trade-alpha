# Momentum Weighting: Score → Price Direction

## Motivation

Current momentum weighting uses the ratio of positive scores in a lookback window:

```
bonus = (positive_score_days / window) * max_momentum_bonus
```

This is redundant because scores already encode model predictions. A better signal is
whether the **stock price itself** has been rising recently — consecutive up-close days
indicate real market momentum and deserve a ranking boost.

## Design

### New Logic

Replace the score-buffer approach with price-direction counting using the same
historical close-price data already loaded for trend bonus and volatility penalty.

```
close_prices: [c1, c2, ..., cN]          # N+1 prices over N days (loaded once per _predict)
up_days = 0
for i in range(1, len(close_prices)):
    if close_prices[i] > close_prices[i-1]:
        up_days += 1

ratio = up_days / N                        # how many days the stock closed up
bonus = min(ratio * max_momentum_bonus, max_momentum_bonus)
score = score + bonus
```

### Affected Files

| File | Change |
|------|--------|
| `pipeline.py` `_predict()` | Add `momentum_window` to `lookback` so price data is loaded when momentum is enabled |
| `pipeline.py` `_apply_momentum_boost()` | Accept `close_prices_hist: Dict[str, List[float]]`, replace score-buffer logic with price-direction logic |
| `pipeline.py` | Remove `_score_buffer_momentum` (no longer needed) |
| `pipeline.py` `run_live()` | Same changes as `_predict` |
| `StrategyConfigView.vue` | Update chip hint: "连续正向评分加成" → "连续上涨天数加成" |

### Data Flow

1. `_predict()` calculates `lookback = max(trend_bonus_window, vol_penalty_window, momentum_window)`
2. If `lookback > 0`, `peek_history_data()` loads historical prices once
3. `close_prices_hist` is passed to `_apply_trend_bonus`, `_apply_volatility_penalty`, and `_apply_momentum_boost`
4. Each method reads from the same pre-loaded data — no extra DB queries

### Field / Config Changes

**None.** The existing fields `use_momentum_boost`, `momentum_window`, `max_momentum_bonus`
keep their names and default values. Only the internal calculation changes.

### Execution Order

Unchanged:

```
compute_scores → _smooth_scores → _apply_trend_bonus → _apply_volatility_penalty → _apply_momentum_boost → _filter_explosions
```