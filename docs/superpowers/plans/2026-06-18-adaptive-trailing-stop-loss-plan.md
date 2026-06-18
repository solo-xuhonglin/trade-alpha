# Adaptive Trailing Stop-Loss Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fixed cost-basis stop-loss with trailing-peak stop-loss adjusted by baseline volatility multiplier.

**Architecture:** Add `peak_price` to `PositionEmbed`, move stop-loss logic to `PortfolioManager`, compute `baseline_vol_multiplier` in `ScoreManager.compute_market_regime()`, pass through `MarketDataEmbed` → strategy → modes → `PortfolioManager.is_stop_loss_triggered()`. Show `baseline_vol_multiplier` in frontend market analysis chart, default hidden.

**Tech Stack:** Python 3.14+ (backend), Vue 3 + ECharts (frontend), MongoDB (snapshot persistence)

---

### Task 1: PositionEmbed — Add `peak_price` field

**Files:**
- Modify: `backend/src/trade_alpha/dao/position.py:6-20`

- [ ] **Step 1: Add `peak_price` field with default 0.0**

```python
class PositionEmbed(BaseModel):
    """Position snapshot for daily record."""

    ts_code: str
    stock_name: str
    buy_date: str
    buy_price: float
    shares: int
    fee: float
    entry_score: float
    entry_3d_prob: float = 0.0
    entry_5d_prob: float = 0.0
    entry_10d_prob: float = 0.0
    entry_20d_prob: float = 0.0
    hold_days: int = 0
    peak_price: float = 0.0  # NEW: Highest close price since purchase
```

- [ ] **Step 2: Verify no syntax errors**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.dao.position import PositionEmbed; print('OK')"`
Expected: prints "OK"

---

### Task 2: PortfolioManager — Add stop-loss methods

**Files:**
- Modify: `backend/src/trade_alpha/execution/portfolio.py`

- [ ] **Step 1: Add `update_peak_prices()` method**

After `get_market_value()` (line 222), add:

```python
def update_peak_prices(self, close_prices: Dict[str, float]) -> None:
    """Update peak price for all positions from today's close prices."""
    for ts_code, pos in self.positions.items():
        current = close_prices.get(ts_code)
        if current is not None and current > pos.peak_price:
            pos.peak_price = current
```

- [ ] **Step 2: Add `is_stop_loss_triggered()` method**

After `update_peak_prices()`, add:

```python
def is_stop_loss_triggered(
    self,
    ts_code: str,
    close_prices: Dict[str, float],
    stop_loss_pct: float,
    vol_multiplier: float = 1.0,
) -> bool:
    """Check if position has hit stop-loss based on peak drawdown or cost floor.

    Two checks (OR-ed):
      1. Trailing stop: current price < peak_price × (1 + stop_loss_pct × vol_multiplier)
      2. Cost floor:    current price < cost_basis × (1 + stop_loss_pct)
    """
    position = self.positions.get(ts_code)
    if position is None:
        return False
    current_price = close_prices.get(ts_code)
    if current_price is None:
        return False

    # 1. Trailing stop: drawdown from peak, adjusted by volatility
    effective_stop = stop_loss_pct * vol_multiplier
    if current_price < position.peak_price * (1 + effective_stop):
        return True

    # 2. Cost floor: never exceed base stop-loss from cost basis
    cost_basis = (position.buy_price * position.shares + position.fee) / position.shares
    if cost_basis <= 0:
        return False
    return current_price < cost_basis * (1 + stop_loss_pct)
```

- [ ] **Step 3: Initialize `peak_price` in `_upsert_position()`**

In `_upsert_position()` (line 166), add `peak_price=matched_price` to both the new-position and merged-position branches:

```python
# New position branch (line 183)
self.positions[ts_code] = PositionEmbed(
    ts_code=ts_code, stock_name=stock_name,
    buy_date="", buy_price=matched_price,
    shares=order_shares, fee=matched_fee,
    peak_price=matched_price,  # NEW
    entry_score=0, entry_3d_prob=0, entry_5d_prob=0, entry_10d_prob=0, entry_20d_prob=0, hold_days=0,
)

# Merged position branch (line 175)
self.positions[ts_code] = PositionEmbed(
    ts_code=ts_code, stock_name=existing.stock_name,
    buy_date=existing.buy_date, buy_price=round(avg_price, 2),
    shares=total_shares, fee=total_fee,
    peak_price=max(existing.peak_price, matched_price),  # NEW: preserve higher peak
    entry_score=0, entry_3d_prob=0, entry_5d_prob=0,
    hold_days=existing.hold_days,
)
```

- [ ] **Step 4: Verify syntax**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.execution.portfolio import PortfolioManager; print('OK')"`
Expected: prints "OK"

---

### Task 3: StrategyConfig — Add volatility window params

**Files:**
- Modify: `backend/src/trade_alpha/dao/strategy_config.py`

- [ ] **Step 1: Add two new fields to `StrategyConfig`**

After `phase_recovery_threshold: float = -0.03` (line 60), add:

```python
    baseline_vol_window: int = 20
    baseline_vol_ref_multiplier: int = 3
```

- [ ] **Step 2: Verify**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.dao.strategy_config import StrategyConfig; print('OK')"`
Expected: prints "OK"

---

### Task 4: MarketDataEmbed — Add `baseline_vol_multiplier`

**Files:**
- Modify: `backend/src/trade_alpha/schemas.py:89-100`

- [ ] **Step 1: Add field**

```python
class MarketDataEmbed(BaseModel):
    """Market regime and ranking statistics for strategy decisions."""
    ranking_high_pct: float = 0.0
    ranking_low_pct: float = 0.0
    top_n_retention_rate: float = 0.0
    top_n_retention_rate_smoothed: float = 0.0
    score_return_corr: float = 0.0
    score_return_corr_smoothed: float = 0.0
    daily_rebalanced_cum: float = 0.0
    position_multiplier: float = 1.0
    buy_threshold_multiplier: float = 1.0
    market_phase: str = ""
    baseline_vol_multiplier: float = 1.0  # NEW
```

- [ ] **Step 2: Verify**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.schemas import MarketDataEmbed; print('OK')"`
Expected: prints "OK"

---

### Task 5: ExecutionDailySnapshot — Add `baseline_vol_multiplier`

**Files:**
- Modify: `backend/src/trade_alpha/dao/execution_daily_snapshot.py`

- [ ] **Step 1: Add field after `market_phase`**

```python
    market_phase: str = ""
    baseline_vol_multiplier: float = 1.0  # NEW
    position_pct: float = 0.0
```

Note: This is near line 32-33. The snapshot will be automatically populated by `_save_snapshot()` which does `updates = dict(self.score_manager.last_market_data)`.

- [ ] **Step 2: Verify**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.dao.execution_daily_snapshot import ExecutionDailySnapshot; print('OK')"`
Expected: prints "OK"

---

### Task 6: ScoreManager — Compute `baseline_vol_multiplier`

**Files:**
- Modify: `backend/src/trade_alpha/execution/scoring.py` (in `compute_market_regime()`)

- [ ] **Step 1: Read existing `compute_market_regime()` to find insertion point**

```python
# Find the method and identify where market_data is built
```

- [ ] **Step 2: Add vol multiplier computation**

Inside `compute_market_regime()`, after existing market data fields are computed, add:

```python
# --- Baseline volatility multiplier for adaptive stop-loss ---
window = getattr(self._strategy_config, 'baseline_vol_window', 20)
ref_mult = getattr(self._strategy_config, 'baseline_vol_ref_multiplier', 3)
ref_window = window * ref_mult

if len(self._daily_rebalanced_cum) >= ref_window:
    # Compute daily returns from cumulative baseline
    cum = self._daily_rebalanced_cum
    returns = [(cum[i] - cum[i-1]) / cum[i-1] for i in range(-ref_window, 0)]
    rolling_vol = np.std(returns[-window:])  # type: ignore[arg-type]
    ref_vol = np.std(returns)                # type: ignore[arg-type]
    if ref_vol > 0:
        multiplier = rolling_vol / ref_vol
        market_data.baseline_vol_multiplier = max(0.5, min(3.0, multiplier))
    else:
        market_data.baseline_vol_multiplier = 1.0
else:
    market_data.baseline_vol_multiplier = 1.0
```

Note: Need to ensure `import numpy as np` is at top of file (it already uses `math` only — check if np import exists; if not, add it).

- [ ] **Step 3: Check numpy import — add if missing**

```python
# At top of scoring.py, after existing imports
import numpy as np
```

- [ ] **Step 4: Verify**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.execution.scoring import ScoreManager; print('OK')"`
Expected: prints "OK"

---

### Task 7: MultiStockStrategy — Wire up new stop-loss

**Files:**
- Modify: `backend/src/trade_alpha/strategy/multi_stock_strategy.py`

- [ ] **Step 1: In `make_orders()`, add peak price update and extract `vol_multiplier`**

Before `mode.settle_mode_orders()` call (around line 77), add:

```python
# Update peak prices before stop-loss check
if close_prices:
    ctx.portfolio.update_peak_prices(close_prices)

vol_multiplier = market_data.baseline_vol_multiplier if market_data else 1.0
```

Pass `vol_multiplier` to `settle_mode_orders()`:

```python
return await mode.settle_mode_orders(
    scored_stocks, trade_date, ctx,
    close_prices, market_data,
    suggestion_mode=suggestion_mode,
    vol_multiplier=vol_multiplier,  # NEW
)
```

- [ ] **Step 2: Remove `_is_stop_loss_triggered()` static method**

Delete the entire method (lines 126-139):

```python
# DELETE this entire block:
# @staticmethod
# def _is_stop_loss_triggered(...):
```

- [ ] **Step 3: Add `PortfolioManager` import for type annotation**

Add to imports in `multi_stock_strategy.py`:

```python
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from trade_alpha.execution.portfolio import PortfolioManager
```

This avoids circular import at runtime while enabling the type annotation in `_check_sell`.

- [ ] **Step 4: Update `_check_sell` signature — add `portfolio` and `vol_multiplier` params**

```python
def _check_sell(
    self,
    position: PositionEmbed,
    top_ts_codes: set,
    sell_rank_ts_codes: set,
    score_map: Dict[str, float],
    close_prices: Optional[Dict[str, float]] = None,
    market_data: Optional[MarketDataEmbed] = None,
    portfolio: Optional["PortfolioManager"] = None,  # NEW
    vol_multiplier: float = 1.0,                     # NEW
) -> Tuple[bool, str]:
```

Also remove the `effective_stop_loss = self.stop_loss_pct` line (line 237) since `self.stop_loss_pct` is passed directly.

- [ ] **Step 4: Update body to use `portfolio.is_stop_loss_triggered()`**

Replace the old `self._is_stop_loss_triggered(position, close_prices, effective_stop_loss)` calls:

```python
# First occurrence (line 240, inside hold_days < min_hold_days check)
if close_prices and portfolio and portfolio.is_stop_loss_triggered(
    position.ts_code, close_prices, self.stop_loss_pct, vol_multiplier,
):
    return True, SELL_REASON_STOP_LOSS

# Second occurrence (line 254, after max_hold_days check)
if close_prices and portfolio and portfolio.is_stop_loss_triggered(
    position.ts_code, close_prices, self.stop_loss_pct, vol_multiplier,
):
    return True, SELL_REASON_STOP_LOSS
```

- [ ] **Step 5: Update TrendMode call to pass `portfolio`**

In TrendMode `settle_mode_orders`, add `portfolio=ctx.portfolio, vol_multiplier=vol_multiplier` (see Task 8).

---

### Task 8: TrendMode / RotationMode — Accept and pass `vol_multiplier`

**Files:**
- Modify: `backend/src/trade_alpha/strategy/modes/trend_mode.py`
- Modify: `backend/src/trade_alpha/strategy/modes/rotation_mode.py`

- [ ] **Step 1: TrendMode — accept `vol_multiplier` in `settle_mode_orders`**

```python
async def settle_mode_orders(
    self,
    scored_stocks: List[ScoredStock],
    trade_date: str,
    ctx: PipelineContext,
    close_prices: Optional[Dict[str, float]] = None,
    market_data: Optional[MarketDataEmbed] = None,
    suggestion_mode: bool = False,
    vol_multiplier: float = 1.0,  # NEW
) -> List[PendingOrder]:
```

Pass these to `_check_sell()`:

```python
# Inside the sell loop, change:
should_sell, sell_reason = self._strategy._check_sell(
    pos, top_ts_codes, sell_rank_ts_codes, score_map, close_prices, market_data,
    portfolio=ctx.portfolio,
    vol_multiplier=vol_multiplier,
)
```

- [ ] **Step 2: RotationMode — accept `vol_multiplier` in `settle_mode_orders`**

```python
async def settle_mode_orders(
    self,
    scored_stocks: List[ScoredStock],
    trade_date: str,
    ctx: PipelineContext,
    close_prices: Optional[Dict[str, float]] = None,
    market_data: Optional[MarketDataEmbed] = None,
    suggestion_mode: bool = False,
    vol_multiplier: float = 1.0,  # NEW
) -> List[PendingOrder]:
```

Pass it to `_check_sell()`:

```python
# Inside the sell loop, change:
should_sell, reason = self._check_sell(pos, close_prices, score_map, portfolio, vol_multiplier)
```

- [ ] **Step 3: RotationMode._check_sell — accept and use `portfolio` + `vol_multiplier`**

Also add `TYPE_CHECKING` import for `PortfolioManager`:
```python
from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from trade_alpha.constants import (
    SELL_REASON_MAX_HOLD_DAYS,
    SELL_REASON_SCORE_BELOW,
    SELL_REASON_STOP_LOSS,
)
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.logging import get_logger
from trade_alpha.schemas import ScoredStock, PendingOrder, MarketDataEmbed
from trade_alpha.execution.context import PipelineContext
from trade_alpha.strategy.modes.base import PhaseMode

if TYPE_CHECKING:
    from trade_alpha.execution.portfolio import PortfolioManager
```

Then update `_check_sell` method:

```python
def _check_sell(
    self,
    position: PositionEmbed,
    close_prices: Dict[str, float],
    score_map: Dict[str, float],
    portfolio: "PortfolioManager",  # NEW
    vol_multiplier: float = 1.0,   # NEW
) -> Tuple[bool, str]:
    """Sell check for rotation mode: stop_loss -> min_hold -> score -> max_hold."""
    strategy = self._strategy

    if portfolio.is_stop_loss_triggered(
        position.ts_code, close_prices, strategy.stop_loss_pct, vol_multiplier,
    ):
        return True, SELL_REASON_STOP_LOSS
    # ... rest unchanged ...
```

---

### Task 9: Verify backend integration tests pass

- [ ] **Step 1: Run existing integration tests**

Run: `cd backend && .venv\Scripts\pytest tests\trade_alpha\integration\ -v --tb=short`
Expected: All 87 tests pass (vol_multiplier=1.0 fallback means no behavioral change when market data unavailable)

If any test fails, fix the issue before proceeding.

---

### Task 10: Frontend — Add `baseline_vol_multiplier` to market analysis chart

**Files:**
- Modify: `frontend/src/components/OverviewChart.vue`
- Modify: `frontend/src/views/BacktestRecordsView.vue`

- [ ] **Step 1: BacktestRecordsView.vue — Map data**

In `loadMarketData()`, add to the map function (around line 1355):

```typescript
marketChartData.value = snaps.map((s, i) => ({
  // ... existing ...
  baseline_vol_multiplier: s.baseline_vol_multiplier ?? 1.0,
}))
```

- [ ] **Step 2: OverviewChart.vue — Add to interface**

```typescript
export interface OverviewChartItem {
  // ... existing ...
  baseline_vol_multiplier: number
}
```

- [ ] **Step 3: OverviewChart.vue — Add new Y-axis**

In the `yAxis` array, add a new axis:

```typescript
{
  id: 'vol_mult',
  type: 'value',
  min: 0,
  max: 3.5,
  name: '止损乘数',
  position: 'right' as const,
  offset: 120,
  axisLabel: { formatter: (v: number) => v.toFixed(1) + 'x' },
},
```

Note: increase the `right` padding in `grid` to accommodate the extra Y axis (currently `'19%'`, might need `'25%'`).

- [ ] **Step 4: OverviewChart.vue — Add series data**

In the `series` array, add:

```typescript
const volMults = props.data.map(d => d.baseline_vol_multiplier)

// New series entry:
{
  name: '止损波动率乘数',
  type: 'line',
  data: volMults,
  yAxisId: 'vol_mult',
  smooth: true,
  lineStyle: { width: 1.5, color: '#e91e63' },
  itemStyle: { color: '#e91e63' },
  symbol: 'none',
},
```

- [ ] **Step 5: OverviewChart.vue — Add legend entry, default hidden**

```typescript
legend: {
  data: [/* ...existing... */, '止损波动率乘数'],
  selected: {
    // ...existing...
    '止损波动率乘数': false,  // NEW: hidden by default
  },
}
```

---

### Task 11: Verify frontend compiles

- [ ] **Step 1: Check TypeScript compilation**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: No type errors

- [ ] **Step 2: Check build**

Run: `cd frontend && npm run build`
Expected: Build succeeds