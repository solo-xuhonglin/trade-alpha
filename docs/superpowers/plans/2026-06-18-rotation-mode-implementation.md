# Rotation Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace MeanReversionMode + DefensiveMode with a single RotationMode using ranking rotation signals for buying.

**Architecture:** flat/down market phases share one RotationMode instance. RotationMode overrides strategy params (min_hold_days=10, sell_threshold=-0.5, full_position_score_window=10). Buy signal uses 3-part ranking history check (was top 10 in 20d~5d, was bottom 10 in 5d, currently rank 70-90).

**Tech Stack:** Python 3.14, asyncio, MongoDB (Beanie ODM), Pydantic v2

---

### Task 1: Add `get_rank_history()` to ScoreManager

**Files:**
- Modify: `backend/src/trade_alpha/execution/scoring.py:612-614`

- [ ] **Step 1: Add the public method after `get_score_buffer`**

Add after line 614:

```python
def get_rank_history(self, ts_code: str) -> List[int]:
    """Return daily rank history for a stock, oldest first."""
    records = self._rank_history.get(ts_code, [])
    return [s.rank for s in records if s.rank > 0]
```

**Note:** Verify the actual `_apply_full_position_sell` call signature in `trend_mode.py` — the method may use `ctx: PipelineContext` instead of individual params. Copy the same calling pattern used by TrendMode.

- [ ] **Step 2: Verify import works**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.execution.scoring import ScoreManager; assert hasattr(ScoreManager, 'get_rank_history') and callable(ScoreManager.get_rank_history); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/execution/scoring.py
git commit -m "feat: add get_rank_history() to ScoreManager"
```

---

### Task 2: Remove `check_common_sell` from MultiStockStrategy

**Files:**
- Modify: `backend/src/trade_alpha/strategy/multi_stock_strategy.py:133-150`

- [ ] **Step 1: Delete `check_common_sell` static method (lines 133-150)**

Remove the entire method block.

- [ ] **Step 2: Verify import works**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy; assert not hasattr(MultiStockStrategy, 'check_common_sell'); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/strategy/multi_stock_strategy.py
git commit -m "refactor: remove check_common_sell static method"
```

---

### Task 3: Remove `SELL_REASON_MEAN_REVERSION` from constants

**Files:**
- Modify: `backend/src/trade_alpha/constants.py:51`

- [ ] **Step 1: Delete line 51**

Remove the `SELL_REASON_MEAN_REVERSION: str = "mean_reversion"` line.

- [ ] **Step 2: Verify import works**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.constants import *; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/constants.py
git commit -m "refactor: remove unused SELL_REASON_MEAN_REVERSION constant"
```

---

### Task 4: Clean StrategyConfig fields

**Files:**
- Modify: `backend/src/trade_alpha/dao/strategy_config.py:61-70`

- [ ] **Step 1: Remove obsolete field definitions**

Delete lines 61-70 (the mr_* block and down_* block), keeping `created_at` and `updated_at`:

Before:
```python
    use_phase_strategy: bool = True
    phase_crash_threshold: float = -0.06
    phase_recovery_threshold: float = -0.03
    # Mean reversion mode (flat market) params
    mr_score_window: int = 20
    mr_exclude_recent_days: int = 5
    mr_mean_reversion_threshold: float = 0.05
    mr_sell_multiplier: float = 1.0
    mr_ranking_window: int = 50
    mr_max_candidates: int = 30
    # Defensive mode (down market) params
    down_sell_threshold: float = 0.0
    down_stop_loss_pct: float = -0.07
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

After:
```python
    use_phase_strategy: bool = True
    phase_crash_threshold: float = -0.06
    phase_recovery_threshold: float = -0.03
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

- [ ] **Step 2: Verify import works**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.dao.strategy_config import StrategyConfig; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/dao/strategy_config.py
git commit -m "refactor: remove obsolete mr_* and down_* strategy config fields"
```

---

### Task 5: Create `rotation_mode.py`

**Files:**
- Create: `backend/src/trade_alpha/strategy/modes/rotation_mode.py`

- [ ] **Step 1: Write the file**

```python
from typing import Dict, List, Optional, Set, Tuple

from trade_alpha.constants import (
    SELL_REASON_MAX_HOLD_DAYS,
    SELL_REASON_SCORE_BELOW,
    SELL_REASON_STOP_LOSS,
)
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.execution.portfolio import PortfolioManager
from trade_alpha.logging import get_logger
from trade_alpha.schemas import ScoredStock, PendingOrder, MarketDataEmbed
from trade_alpha.strategy.modes.base import PhaseMode


logger = get_logger("strategy.modes.rotation_mode")


class RotationMode(PhaseMode):
    """Rotation trading mode for flat + down market phases.

    Buys stocks showing ranking rotation: once top-ranked, fallen to
    bottom, now at potential reversal zone (rank 70-90).
    """

    def __init__(self, strategy: "MultiStockStrategy"):
        super().__init__(strategy)
        strategy.min_hold_days = 10
        strategy.sell_threshold = -0.5
        self._strategy_config.full_position_score_window = 10

    async def settle_mode_orders(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        portfolio: PortfolioManager,
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
        score_manager: Optional["ScoreManager"] = None,
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
        close_prices = close_prices or {}
        score_map = {st.ts_code: st.composite_score for st in scored_stocks}

        for pos in portfolio.positions.values():
            pos.hold_days += 1

        # --- SELL ---
        orders: List[PendingOrder] = []

        for ts_code, pos in portfolio.positions.items():
            should_sell, reason = self._check_sell(pos, close_prices, score_map)
            if should_sell:
                sell_price = close_prices.get(ts_code, pos.buy_price)
                orders.append(PendingOrder(
                    ts_code=pos.ts_code,
                    stock_name=pos.stock_name,
                    order_price=sell_price,
                    order_shares=-pos.shares,
                    entry_score=pos.entry_score,
                    trade_date=trade_date,
                    settle_date=self._strategy._next_trade_date(trade_date),
                    reason=reason,
                ))

        forced_orders = self._strategy._apply_full_position_sell(
            scored_stocks, close_prices, trade_date, market_data, score_manager,
        )
        orders.extend(forced_orders)

        # --- BUY (ranking rotation signal) ---
        hold_ts_codes = set(portfolio.positions.keys())
        purchased_ts_codes: Set[str] = set()

        candidates = []
        for st in scored_stocks:
            if st.is_excluded:
                continue
            if st.ts_code in hold_ts_codes:
                continue
            if not (70 <= st.rank <= 90):
                continue

            rank_history = score_manager.get_rank_history(st.ts_code) if score_manager else []
            if len(rank_history) < 6:
                continue
            was_top = any(r <= 10 for r in rank_history[:-5])
            recent_bottom = any(r >= 91 for r in rank_history[-5:])
            if not (was_top and recent_bottom):
                continue
            candidates.append(st)

        candidates.sort(key=lambda s: s.rank)

        position_multiplier = 1.0

        for stock in candidates:
            if stock.ts_code in purchased_ts_codes:
                continue
            if suggestion_mode:
                if len(portfolio.positions) + 1 > self._strategy.max_positions:
                    break
                purchased_ts_codes.add(stock.ts_code)
                orders.append(self._strategy._build_order(stock, 0, "rotation_buy", trade_date))
                continue
            success, shares, _fee = portfolio.reserve_funds(
                stock.ts_code, stock.close, close_prices, max_position_scalar=position_multiplier,
            )
            if not success:
                continue
            purchased_ts_codes.add(stock.ts_code)
            orders.append(self._strategy._build_order(stock, shares, "rotation_buy", trade_date))

        return orders

    def _check_sell(
        self,
        position: PositionEmbed,
        close_prices: Dict[str, float],
        score_map: Dict[str, float],
    ) -> Tuple[bool, str]:
        """Sell check for rotation mode: stop_loss → min_hold → score → max_hold."""
        strategy = self._strategy

        # 1. stop-loss (always)
        if strategy._is_stop_loss_triggered(position, close_prices, strategy.stop_loss_pct):
            return True, SELL_REASON_STOP_LOSS

        # 2. min hold days protection
        if position.hold_days < strategy.min_hold_days:
            return False, ""

        # 3. score too low
        score = score_map.get(position.ts_code, 0.0)
        if score < strategy.sell_threshold:
            return True, SELL_REASON_SCORE_BELOW

        # 4. max hold days
        if position.hold_days >= strategy.max_hold_days:
            return True, SELL_REASON_MAX_HOLD_DAYS

        return False, ""
```

- [ ] **Step 2: Verify import works**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.strategy.modes.rotation_mode import RotationMode; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Ensure scores are present on ScoredStock**

Note: `st.rank` on each ScoredStock is set during `predict_and_score` → `_record_ranks()` and available in `settle_mode_orders`. No changes needed.

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/strategy/modes/rotation_mode.py
git commit -m "feat: add RotationMode with ranking rotation buy signal"
```

---

### Task 6: Delete obsolete mode files

**Files:**
- Delete: `backend/src/trade_alpha/strategy/modes/mean_reversion_mode.py`
- Delete: `backend/src/trade_alpha/strategy/modes/defensive_mode.py`

- [ ] **Step 1: Delete both files**

```bash
git rm backend/src/trade_alpha/strategy/modes/mean_reversion_mode.py
git rm backend/src/trade_alpha/strategy/modes/defensive_mode.py
```

- [ ] **Step 2: Verify no leftover imports reference them**

Run: `cd backend && .venv\Scripts\python -c "print('checking imports...'); import importlib; importlib.import_module('trade_alpha.strategy.multi_stock_strategy'); print('OK')"`
Expected: `OK` (There should be no unresolved imports if multi_stock_strategy no longer imports them)

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor: remove obsolete MeanReversionMode and DefensiveMode"
```

---

### Task 7: Update MultiStockStrategy wiring

**Files:**
- Modify: `backend/src/trade_alpha/strategy/multi_stock_strategy.py`
  - Replace imports: remove `MeanReversionMode`, `DefensiveMode`, add `RotationMode`
  - Replace `_modes` dict: point flat/down to `RotationMode`
  - Remove `PositionEmbed` import if no longer used
  - Remove unused constants if applicable

- [ ] **Step 1: Update imports (lines 5-22)**

Before:
```python
from trade_alpha.constants import (
    REASON_NORMAL_BUY,
    REASON_PRIORITY_RANK_UP,
    SELL_REASON_FULL_POSITION,
    SELL_REASON_HOLD_SCORE_LOW,
    SELL_REASON_MAX_HOLD_DAYS,
    SELL_REASON_SCORE_BELOW,
    SELL_REASON_STOP_LOSS,
)
...
from trade_alpha.strategy.modes.trend_mode import TrendMode
from trade_alpha.strategy.modes.mean_reversion_mode import MeanReversionMode
from trade_alpha.strategy.modes.defensive_mode import DefensiveMode
```

After:
```python
from trade_alpha.constants import (
    SELL_REASON_FULL_POSITION,
)
...
from trade_alpha.strategy.modes.rotation_mode import RotationMode
from trade_alpha.strategy.modes.trend_mode import TrendMode
```

Note: Keep unused imports for now if they're still referenced elsewhere in the file. Keep `PositionEmbed` if used by `_check_sell`, keep `ScoredStock`, etc. Only remove what's truly unused after checking.

- [ ] **Step 2: Update `_modes` dict (lines 48-52)**

Before:
```python
        self._modes = {
            "up": TrendMode(self),
            "flat": MeanReversionMode(self),
            "down": DefensiveMode(self),
        }
```

After:
```python
        self._modes = {
            "up": TrendMode(self),
            "flat": RotationMode(self),
            "down": RotationMode(self),
        }
```

- [ ] **Step 3: Update `_apply_full_position_sell` signature and callers to pass `ctx`**

Check the current signature - it uses `score_manager` parameter not `ctx`. The plan must match the current code. The current method signature is:
```python
def _apply_full_position_sell(self, scored_stocks, portfolio, close_prices, trade_date, market_data, score_manager):
```
The RotationMode calls:
```python
self._strategy._apply_full_position_sell(
    scored_stocks, portfolio, close_prices, trade_date, market_data, score_manager,
)
```
This matches the current signature used by TrendMode too - no change needed.

- [ ] **Step 4: Verify import works**

Run: `cd backend && .venv\Scripts\python -c "from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/strategy/multi_stock_strategy.py
git commit -m "refactor: wire RotationMode into flat/down phase dispatch"
```

---

### Task 8: Run integration tests

- [ ] **Step 1: Run full integration test suite**

Run: `cd backend && .venv\Scripts\pytest tests\trade_alpha\integration\ -v`
Expected: 126 passed

- [ ] **Step 2: If any test fails, diagnose and fix**

Check the error message. Most likely the tests reference `check_common_sell` or `MeanReversionMode`/`DefensiveMode`. Update any test files that still import the removed classes or methods.

- [ ] **Step 3: Commit final changes**

```bash
git add <any fixed test files>
git commit -m "test: fix test references after RotationMode integration"
```
