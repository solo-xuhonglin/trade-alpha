# Strategy-Mode Refactoring: Decouple + Template Flow

## Problem

### 1. Bidirectional coupling between Strategy and Mode

`MultiStockStrategy` and its modes (`TrendMode`, `RotationMode`) have a bidirectional dependency:

- Modes hold `self._strategy` back-reference and call internal methods: `_build_order()`, `_apply_full_position_sell()`, `_market_multipliers()`, `_score_not_declining()`, `_next_trade_date()`
- Strategy uses `isinstance(mode, RotationMode)` to decide which params to apply, leaking mode implementation into strategy logic

### 2. Duplicated order generation code

Both `TrendMode.settle_mode_orders()` and `RotationMode.settle_mode_orders()` contain nearly identical sell loops and full_position_sell calls. Only the buy candidate selection differs.

## Design

### Core Principle

**Mode = pure stateless stock selector.** It only answers "which stocks should we buy?" The strategy owns the full order flow (sell loop, full position sell, buy processing).

### Architecture

```
PipelineContext
  └── mode_map: Dict[str, PhaseMode]  ← modes are stateless instances

MultiStockStrategy.make_orders()
  ├── 1. Filter scored_stocks
  ├── 2. Select mode from ctx.mode_map[market_phase]
  ├── 3. _apply_mode_params(mode)
  ├── 4. Update peak prices
  ├── 5. Build score_map + increment hold_days
  ├── 6. Compute top_ts_codes + sell_rank_ts_codes
  ├── 7. Sell loop (self.check_sell)
  ├── 8. Full position sell (self._apply_full_position_sell)
  ├── 9. mode.select_buy_candidates() → List[BuyCandidate]
  └── 10. Process buy candidates (reserve_funds + _build_order)
```

### Component Details

#### PhaseMode (abstract base)

```python
class PhaseMode(ABC):
    """Stateless stock selector. No __init__, no strategy back-reference."""

    # Class-level param overrides (None = use strategy_config default)
    min_hold_days: Optional[int] = None
    sell_threshold: Optional[float] = None
    full_position_score_window: Optional[int] = None

    @abstractmethod
    def select_buy_candidates(
        self,
        scored_stocks: List[ScoredStock],
        ctx: PipelineContext,
        market_data: Optional[MarketDataEmbed] = None,
    ) -> List[BuyCandidate]:
        """Return buy candidates sorted by priority (highest first)."""
```

#### BuyCandidate (new schema)

```python
@dataclass
class BuyCandidate:
    """A stock recommended by the mode for purchase."""
    stock: ScoredStock
    reason: str = REASON_NORMAL_BUY
```

#### TrendMode

- `select_buy_candidates()`:
  1. Compute effective params from market_data multipliers (position_multiplier, buy_threshold_multiplier)
  2. Build full_candidates (all scored_stocks sorted by ranking_score) for rank_up check
  3. Filter by composite_score > effective_threshold → sorted → top_stocks
  4. Return: rank_up candidates first (sorted by rank_improvement), then top_stocks (sorted by ranking_score)

- No param overrides (uses strategy_config defaults)

#### RotationMode

- Class-level overrides: `min_hold_days = 10`, `sell_threshold = -0.5`, `full_position_score_window = 10`
- `select_buy_candidates()`:
  1. Skip excluded + already held stocks
  2. Filter by rotation_rank_min ≤ rank ≤ rotation_rank_max
  3. Rank history check: was_top in early history + recent_bottom in last 5 days
  4. Reversal check (optional): today's rank < 5-day average rank
  5. Return candidates sorted by rank ascending

#### MultiStockStrategy

- `_apply_mode_params(mode)`: Read class-level overrides from mode, apply to self
- `make_orders()`: Full orchestration as shown in Architecture above
- All utility methods remain: `_build_order`, `_next_trade_date`, `_score_not_declining`, `_market_multipliers`
- `check_sell()`: Unified for all modes (both modes use the same sell logic)

#### PipelineContext

Add `mode_map: Dict[str, PhaseMode]` parameter with default:

```python
self.mode_map = mode_map or {
    "up": TrendMode(),
    "flat": RotationMode(),
    "down": RotationMode(),
}
```

### Sell Logic Unification

Both modes use the same `MultiStockStrategy.check_sell()`:

1. Before `min_hold_days`: only stop-loss can trigger sell
2. Score below `sell_threshold` → sell
3. Exceeded `max_hold_days` → sell
4. Stop-loss triggered → sell
5. Not in `sell_rank_ts_codes` and score below `hold_score_threshold` → sell

Step 5 applies uniformly to both modes.

## Changeset

| File | Change |
|------|--------|
| `schemas.py` | Add `BuyCandidate` dataclass |
| `modes/base.py` | Rewrite `PhaseMode` as abstract selector, remove `self._strategy` |
| `modes/trend_mode.py` | Rewrite: only `select_buy_candidates()` |
| `modes/rotation_mode.py` | Rewrite: class-level param overrides + `select_buy_candidates()`; remove `check_sell()` |
| `multi_stock_strategy.py` | Expand `make_orders()` with full flow; add `_apply_mode_params()`; remove delegated calls |
| `execution/context.py` | Add `mode_map` field |
| (delete) `modes/rotation_mode.py check_sell` | Unified into strategy's check_sell |

## Non-Changes

- `BaseStrategy` — untouched
- `SingleStockStrategy` — untouched
- Utility methods (`_build_order`, `_next_trade_date`, etc.) — stay as strategy methods
- `check_sell()` signature — unchanged
- `_apply_full_position_sell()` — unchanged
- `_score_not_declining()` — unchanged
- `_market_multipliers()` — unchanged
- Backtest/suggestion pipelines — not affected (they call `strategy.make_orders()` which keeps same signature)