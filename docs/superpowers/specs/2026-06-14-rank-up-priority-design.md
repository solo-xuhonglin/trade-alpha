# Rank-Up Priority Buy Design

## Summary

Add a toggleable buy rule that prioritizes stocks with improving rank (rank trending upward) over the current pure ranking-score-based buy logic. Buy reasons are separated: `priority_rank_up` vs `normal_buy`. If not enough rank-up stocks meet criteria, remaining slots fall through to the existing logic.

## Background

Current `MultiStockStrategy.make_decisions()` buys top N stocks by `ranking_score` descending. In choppy/oscillating markets, top-ranked stocks may have peaked in rank — buying them means buying near a local high. Stocks with improving rank (recent average rank worse than current rank) signal upward momentum in the ranking itself.

## Parameters

All parameters are in the "交易优化" group of strategy config.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `use_rank_up_priority` | `bool` | `False` | Enable rank-up priority buy |
| `rank_up_window` | `int` | `5` | Days for average rank computation |
| `rank_up_count` | `int` | `3` | Max number of priority rank-up buys per day |
| `rank_up_min_score` | `float` | `0.1` | Minimum score threshold for rank-up buys |
| `rank_up_min_improvement_pct` | `float` | `0.20` | Minimum rank improvement as percentage (e.g., 0.20 = 20%) |

## Decoupling Architecture

```
Pipeline (backtest_pipeline / suggestion_pipeline)
    │
    ├── RankHistoryTracker  (new standalone utility)
    │       Manages cross-day rank buffer
    │       compute_improvement(ts_code, current_rank, window) → float | None
    │
    ├── ScoredStock  (dataclass in schemas.py)
    │       + rank: int
    │       + rank_improvement: float
    │
    └── MultiStockStrategy.make_decisions()
            Two-phase buy logic:
              Phase 1: rank_up candidates (reason="priority_rank_up")
              Phase 2: remaining via existing logic (reason="normal_buy")
```

### Dependency Flow

```
Pipeline scores & ranks stocks
    → RankHistoryTracker.record_day(date, {ts_code: rank})
    → Pipeline computes rank_improvement per stock via tracker
    → ScoredStock carries rank + rank_improvement
    → Strategy uses rank_improvement in buy decisions
```

## Component Design

### 1. RankHistoryTracker

File: `backend/src/trade_alpha/execution/rank_tracker.py`

```python
class RankHistoryTracker:
    """Cross-day rank history for computing rank improvement.

    Maintains per-stock rank history across trading days.
    Used by pipeline to attach rank_improvement to scored stocks
    before passing to strategy decisions.

    Usage:
        tracker = RankHistoryTracker()
        # After daily ranking:
        tracker.record_day(date, {ts_code: rank, ...})
        # For each stock before strategy call:
        improvement = tracker.compute_improvement(ts_code, current_rank, window=5)
    """

    def __init__(self):
        self._history: Dict[str, List[int]] = {}

    def record_day(self, date: str, ranks: Dict[str, int]) -> None:
        """Record today's ranks for all stocks. Clears entries for new date."""
        self._last_date = date
        for ts_code, rank in ranks.items():
            self._history.setdefault(ts_code, []).append(rank)

    def compute_improvement(self, ts_code: str, current_rank: int, window: int) -> Optional[float]:
        """Compute rank improvement as (avg_past_rank - current_rank) / max(1, avg_past_rank).

        Uses the last `window` entries excluding today (the most recent entry).
        Returns None if insufficient history.
        Positive value means rank is improving (current rank better than recent avg).
        """
        records = self._history.get(ts_code, [])
        # Need at least 2 entries total to have a "past" (today + at least 1 past day)
        if len(records) < 2:
            return None
        # Get past entries (exclude today = last entry)
        past = records[-(window + 1):-1] if len(records) > window + 1 else records[:-1]
        if not past:
            return None
        avg_past = sum(past) / len(past)
        return (avg_past - current_rank) / max(1.0, avg_past)

    def get_rank(self, ts_code: str, days_ago: int = 0) -> Optional[int]:
        """Get rank for a stock at a given offset (0=today)."""
        records = self._history.get(ts_code, [])
        if not records:
            return None
        idx = -1 - days_ago
        if abs(idx) > len(records):
            return None
        return records[idx]
```

Notes:
- Not async — pure in-memory computation
- No dependencies on pipeline or strategy classes
- Easy to test independently

### 2. ScoredStock — New Fields

File: `backend/src/trade_alpha/schemas.py`

```python
@dataclass
class ScoredStock:
    ...
    price_avg_range: float = 0.0
    rank: int = 0           # NEW: current day rank
    rank_improvement: float = 0.0  # NEW: improvement pct
```

### 3. Pipeline Changes

#### backtest_pipeline.py

After scoring/ranking (around `_record_ranks` / after `smooth_scores`):
- Create `RankHistoryTracker` in pipeline `__init__` or `run()`
- After assigning ranks each day: `self._rank_tracker.record_day(date, rank_map)`
- Before strategy.make_decisions: attach `rank_improvement` to each ScoredStock
- `rank_improvement` = 0.0 when history insufficient or feature disabled

#### suggestion_pipeline.py

Same pattern — after ranking, attach rank_improvement before strategy call.

### 4. Strategy Changes

File: `backend/src/trade_alpha/strategy/multi_stock_strategy.py`

`MultiStockStrategy` receives new strategy config params:

```python
self.use_rank_up_priority = strategy_config.use_rank_up_priority
self.rank_up_window = strategy_config.rank_up_window
self.rank_up_count = strategy_config.rank_up_count
self.rank_up_min_score = strategy_config.rank_up_min_score
self.rank_up_min_improvement_pct = strategy_config.rank_up_min_improvement_pct
```

**Buy flow (modified `make_decisions`):**

```
1. scored_stocks 过滤(score > buy_threshold + !is_excluded)
2. 按 ranking_score 降序排序 → sorted_stocks

3. Phase 1 — Rank-up priority (if use_rank_up_priority):
   a. 从 sorted_stocks 中筛选:
      rank_improvement >= rank_up_min_improvement_pct
      AND score > rank_up_min_score
   b. 按 rank_improvement 降序排序
   c. 取 top rank_up_count, 生成 reason="priority_rank_up"
   d. 占位: rank_up_purchased = len(这些)

4. Phase 2 — Normal fill (always runs):
   a. 从 sorted_stocks 中排除 Phase 1 已买的
   b. 取 top (max_positions - rank_up_purchased)
   c. reserve_funds → 生成 reason="normal_buy"

5. 两个阶段合并后 + sell orders = orders
```

Both phases respect existing constraints:
- Phase 1 skips held stocks
- Phase 2 skips held + Phase 1 purchased stocks
- Both check max_positions capacity
- Both respect reserve_funds (backtest) / suggestion_count (suggestion)

### 5. DAO — StrategyConfig Fields

File: `backend/src/trade_alpha/dao/strategy_config.py`

Insert after `use_acceleration_filter` block:

| Field | Type | Default |
|-------|------|---------|
| `use_rank_up_priority` | `bool` | `False` |
| `rank_up_window` | `int` | `5` |
| `rank_up_count` | `int` | `3` |
| `rank_up_min_score` | `float` | `0.1` |
| `rank_up_min_improvement_pct` | `float` | `0.20` |

### 6. API Schema

File: `backend/src/trade_alpha/api/schemas.py`

- `StrategyCreateRequest`: add all 5 fields with defaults
- `StrategyUpdateRequest`: add all 5 fields as `Optional[type] = None`

### 7. Frontend

#### StrategyConfigView.vue

New section in "交易优化" tab (after 加速排除).

Layout:
```
[use_rank_up_priority v-switch 排名上涨优先]
排名窗口 [__5__]    优先买入数 [__3__]
最低评分 [__0.1__]  最小提升 [__20__]% (step=5)
```

- Params disabled when `use_rank_up_priority` is off
- `rank_up_min_improvement_pct` displayed as percentage (0.20 → 20)

#### StrategyChips.vue

Add chip (similar to existing pattern):
```
排名上涨 [chip: mdi-check/mdi-close]
```

form defaults, openDialog copy, saveStrategy — same pattern as previous task.

### 8. PendingOrder / Trade Reason

Two new reason constants:

```python
# In constants.py or inline:
REASON_PRIORITY_RANK_UP = "priority_rank_up"
REASON_NORMAL_BUY = "normal_buy"
```

- `PendingOrder.reason` for rank-up buys = `"priority_rank_up"`
- `PendingOrder.reason` for normal fill = `"normal_buy"` (currently empty string, this is a minor upgrade for clarity)

### 9. ScoredStock serialization

- `suggestion_pipeline.py` live_daily_stock_score insert: no new fields needed (rank/improvement are ephemeral, not persisted to DB)
- LiveOrderSuggestion insert: no new fields needed
- backtest_pipeline.py ScoredStock → snapshot: rank/improvement are ephemeral

## Mutex Rules

- `use_rank_up_priority` is independent of all other switches
- When enabled: Phase 1 always runs first, Phase 2 fills remaining slots
- When disabled: existing pure ranking logic unchanged
- Phase 1 + Phase 2 combined still respects `max_positions` total

## Why This Is Decoupled

1. **RankHistoryTracker** is a standalone utility — zero dependencies on pipeline or strategy
2. **ScoredStock** only gains 2 data fields — no behavioral change
3. **Pipeline** only adds: create tracker → record_day → compute → attach — minimal, composable
4. **Strategy** only reads `rank_improvement` from ScoredStock — doesn't know how it was computed
5. Each piece can be tested in isolation
