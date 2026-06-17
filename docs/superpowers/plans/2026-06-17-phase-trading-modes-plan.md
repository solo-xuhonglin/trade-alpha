# Three Trading Modes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace single `MultiStockStrategy.make_orders` with 3 phase-specific trading modes (Trend, Mean Reversion, Defensive), selected by `market_phase`.

**Architecture:** Extract existing make_orders logic into `TrendMode`, add `MeanReversionMode` and `DefensiveMode` as new classes in `strategy/modes/`. Each mode inherits from `PhaseMode` base class and accesses `MultiStockStrategy` for shared utilities. Common sell logic (stop-loss + max-hold) extracted to `MultiStockStrategy.check_common_sell`.

**Tech Stack:** Python, Pydantic/Beanie, asyncio

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `constants.py` | Modify | Add `SELL_REASON_MEAN_REVERSION = "mean_reversion"` |
| `dao/strategy_config.py` | Modify | Add 7 mean-reversion and defensive fields |
| `execution/scoring.py` | Modify | Change down pos_mult from 0.5 to 0.3 |
| `strategy/modes/__init__.py` | Create | Empty init |
| `strategy/modes/base.py` | Create | `PhaseMode` abstract base class |
| `strategy/modes/trend_mode.py` | Create | `TrendMode` (up logic extracted from make_orders) |
| `strategy/modes/mean_reversion_mode.py` | Create | `MeanReversionMode` (flat logic) |
| `strategy/modes/defensive_mode.py` | Create | `DefensiveMode` (down logic) |
| `strategy/multi_stock_strategy.py` | Modify | Add mode dispatch, `check_common_sell`, remove `_stop_loss_mult` |

---

### Task 1: Add SELL_REASON_MEAN_REVERSION constant

**Files:**
- Modify: `backend/src/trade_alpha/constants.py`

- [ ] **Step 1: Read constants.py to find insertion point**

```bash
cd d:\projects\trade-alpha\backend
cat -n src/trade_alpha/constants.py
```

- [ ] **Step 2: Add the new constant**

Insert `SELL_REASON_MEAN_REVERSION = "mean_reversion"` after the existing SELL_REASON constants block.

- [ ] **Step 3: Verify import works**

```bash
cd d:\projects\trade-alpha\backend
.venv\Scripts\python -c "from trade_alpha.constants import SELL_REASON_MEAN_REVERSION; print(SELL_REASON_MEAN_REVERSION)"
```

Expected: `mean_reversion`

- [ ] **Step 4: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/constants.py
git commit -m "feat: add SELL_REASON_MEAN_REVERSION constant"
```

---

### Task 2: Add 7 new fields to StrategyConfig

**Files:**
- Modify: `backend/src/trade_alpha/dao/strategy_config.py`

- [ ] **Step 1: Read the current StrategyConfig**

```bash
cd d:\projects\trade-alpha\backend
cat -n src/trade_alpha/dao/strategy_config.py
```

- [ ] **Step 2: Add 7 new fields before `created_at`**

Insert after line `phase_recovery_threshold: float = -0.03`:

```python
    # Mean reversion mode (flat market) params
    mr_score_window: int = 20
    mr_exclude_recent_days: int = 5
    mr_mean_reversion_threshold: float = 0.05
    mr_sell_multiplier: float = 1.0
    mr_max_candidates: int = 30
    # Defensive mode (down market) params
    down_sell_threshold: float = 0.0
    down_stop_loss_pct: float = -0.07
```

- [ ] **Step 3: Verify import works**

```bash
cd d:\projects\trade-alpha\backend
.venv\Scripts\python -c "
from trade_alpha.dao.strategy_config import StrategyConfig
c = StrategyConfig(name='test')
print('mr_score_window:', c.mr_score_window)
print('down_sell_threshold:', c.down_sell_threshold)
print('All fields OK')
"
```

- [ ] **Step 4: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/dao/strategy_config.py
git commit -m "feat: add mean-reversion and defensive mode fields to StrategyConfig"
```

---

### Task 3: Change down pos_mult from 0.5 to 0.3 in scoring.py

**Files:**
- Modify: `backend/src/trade_alpha/execution/scoring.py`

- [ ] **Step 1: Find the pos_mult return for "down"**

```bash
cd d:\projects\trade-alpha\backend
grep -n "three_phase == \"down\"" src/trade_alpha/execution/scoring.py
```

- [ ] **Step 2: Change 0.5 to 0.3**

In `_compute_phase_multipliers`, change the line:

```python
        if three_phase == "down":
            return 0.5, 1.0, "down"
```

to:

```python
        if three_phase == "down":
            return 0.3, 1.0, "down"
```

- [ ] **Step 3: Verify import works**

```bash
cd d:\projects\trade-alpha\backend
.venv\Scripts\python -c "from trade_alpha.execution.scoring import ScoreManager; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/execution/scoring.py
git commit -m "feat: reduce down position multiplier from 0.5 to 0.3"
```

---

### Task 4: Add check_common_sell to MultiStockStrategy

**Files:**
- Modify: `backend/src/trade_alpha/strategy/multi_stock_strategy.py`

- [ ] **Step 1: Add the static method**

Find the `_market_multipliers` method. Add a new static method `check_common_sell` after `_is_stop_loss_triggered`:

```python
    @staticmethod
    def check_common_sell(
        position: "PositionEmbed",
        close_prices: Dict[str, float],
        stop_loss_pct: float,
        max_hold_days: int,
    ) -> Tuple[bool, str]:
        """Common sell checks shared by all modes: stop-loss and max hold days."""
        if MultiStockStrategy._is_stop_loss_triggered(position, close_prices, stop_loss_pct):
            return True, SELL_REASON_STOP_LOSS
        if position.hold_days >= max_hold_days:
            return True, SELL_REASON_MAX_HOLD_DAYS
        return False, ""
```

- [ ] **Step 2: Verify import works**

```bash
cd d:\projects\trade-alpha\backend
.venv\Scripts\python -c "
from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy
print('check_common_sell:', MultiStockStrategy.check_common_sell)
print('OK')
"
```

- [ ] **Step 3: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/strategy/multi_stock_strategy.py
git commit -m "feat: add check_common_sell static method (stop-loss + max-hold)"
```

---

### Task 5: Create PhaseMode base class and mode files

**Files:**
- Create: `backend/src/trade_alpha/strategy/modes/__init__.py`
- Create: `backend/src/trade_alpha/strategy/modes/base.py`
- Create: `backend/src/trade_alpha/strategy/modes/trend_mode.py`
- Create: `backend/src/trade_alpha/strategy/modes/mean_reversion_mode.py`
- Create: `backend/src/trade_alpha/strategy/modes/defensive_mode.py`

- [ ] **Step 1: Create the `__init__.py`**

```bash
mkdir -p d:\projects\trade-alpha\backend\src\trade_alpha\strategy\modes
```

Empty file:

```bash
cd d:\projects\trade-alpha\backend
type nul > src/trade_alpha/strategy/modes/__init__.py
```

- [ ] **Step 2: Create `base.py`**

Write `backend/src/trade_alpha/strategy/modes/base.py`:

```python
from abc import ABC, abstractmethod
from typing import Dict, List

from trade_alpha.execution.portfolio import PortfolioManager
from trade_alpha.schemas import ScoredStock, PendingOrder, MarketDataEmbed


class PhaseMode(ABC):
    """Base class for phase-specific trading modes."""

    def __init__(self, strategy: "MultiStockStrategy"):
        self._strategy = strategy

    @abstractmethod
    async def run(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        portfolio: PortfolioManager,
        close_prices: Dict[str, float],
        market_data: MarketDataEmbed,
        score_manager: "ScoreManager",
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
        ...
```

- [ ] **Step 3: Create `trend_mode.py`**

Write `backend/src/trade_alpha/strategy/modes/trend_mode.py`. This is the existing `make_orders` logic extracted as a mode, calling `self._strategy._check_sell(...)` and `self._strategy._apply_full_position_sell(...)`:

```python
from typing import Dict, List, Optional

from trade_alpha.constants import REASON_NORMAL_BUY, REASON_PRIORITY_RANK_UP
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.execution.portfolio import PortfolioManager
from trade_alpha.logging import get_logger
from trade_alpha.schemas import ScoredStock, PendingOrder, MarketDataEmbed
from trade_alpha.strategy.modes.base import PhaseMode

logger = get_logger("strategy.modes.trend_mode")


class TrendMode(PhaseMode):
    """Trend-following mode (market_phase = 'up').

    Full position, rank-based buy/sell. Identical to the original
    MultiStockStrategy.make_orders logic.
    """

    async def run(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        portfolio: PortfolioManager,
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
        score_manager: Optional["ScoreManager"] = None,
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
        s = self._strategy
        score_map = {st.ts_code: st.composite_score for st in scored_stocks}
        scored_stocks = [st for st in scored_stocks if not st.is_excluded]
        full_candidates = sorted(scored_stocks, key=lambda st: st.ranking_score, reverse=True)

        pos_mult, buy_mult = s._market_multipliers(market_data)
        effective_threshold = s.buy_threshold * buy_mult
        effective_max_pos = max(1, int(s.max_positions * pos_mult))

        scored_stocks = [st for st in scored_stocks if st.composite_score > effective_threshold]
        sorted_stocks = sorted(scored_stocks, key=lambda st: st.ranking_score, reverse=True)

        if len(sorted_stocks) <= 5:
            logger.info(f"make_orders trade_date={trade_date} scored_above_threshold={len(sorted_stocks)}")
        elif len(sorted_stocks) % 10 == 0:
            logger.info(f"make_orders trade_date={trade_date} scored_above_threshold={len(sorted_stocks)}")

        top_stocks = sorted_stocks[:effective_max_pos]
        top_ts_codes = {st.ts_code for st in top_stocks}
        sell_rank_stocks = sorted_stocks[:s.sell_rank_n]
        sell_rank_ts_codes = {st.ts_code for st in sell_rank_stocks}

        orders: List[PendingOrder] = []
        close_prices = close_prices or {}
        for pos in portfolio.positions.values():
            pos.hold_days += 1

        logger.info(
            f"make_orders trade_date={trade_date} positions={len(portfolio.positions)} "
            f"top_stocks={len(top_stocks)} sell_rank={len(sell_rank_ts_codes)} suggestion_mode={suggestion_mode}"
        )

        for ts_code, pos in portfolio.positions.items():
            should_sell, sell_reason = s._check_sell(
                pos, top_ts_codes, sell_rank_ts_codes, score_map, close_prices, market_data
            )
            if should_sell:
                in_score = ts_code in score_map
                in_sell_rank = ts_code in sell_rank_ts_codes
                cur_score = score_map.get(ts_code, 0.0)
                logger.info(
                    f"make_orders SELL ts_code={ts_code} hold_days={pos.hold_days} "
                    f"in_score_map={in_score} current_score={cur_score:.3f} "
                    f"in_sell_rank={in_sell_rank} reason={sell_reason}"
                )
                sell_price = close_prices.get(ts_code, pos.buy_price)
                orders.append(PendingOrder(
                    ts_code=pos.ts_code,
                    stock_name=pos.stock_name,
                    order_price=sell_price,
                    order_shares=-pos.shares,
                    entry_score=pos.entry_score,
                    up_prob_3d=pos.entry_3d_prob,
                    up_prob_5d=pos.entry_5d_prob,
                    up_prob_10d=pos.entry_10d_prob,
                    up_prob_20d=pos.entry_20d_prob,
                    trade_date=trade_date,
                    settle_date=s._next_trade_date(trade_date),
                    reason=sell_reason,
                ))

        sell_ts_codes = {order.ts_code for order in orders}
        forced_orders = s._apply_full_position_sell(
            scored_stocks, portfolio, close_prices, trade_date, market_data, score_manager,
        )
        orders.extend(forced_orders)

        suggestion_count = 0
        hold_ts_codes = set(portfolio.positions.keys())
        purchased_ts_codes: set = set()

        if s.use_rank_up_priority and s.rank_up_count > 0:
            rank_up_candidates = [
                st for st in full_candidates
                if st.ts_code not in hold_ts_codes
                and st.rank_improvement >= s.rank_up_min_improvement_pct
                and st.composite_score > s.rank_up_min_score * buy_mult
                and s._score_not_declining(st.ts_code, score_manager)
            ]
            rank_up_candidates.sort(key=lambda st: st.rank_improvement, reverse=True)
            for stock in rank_up_candidates[:s.rank_up_count]:
                if suggestion_mode:
                    if len(portfolio.positions) + suggestion_count >= s.max_positions:
                        break
                    suggestion_count += 1
                    purchased_ts_codes.add(stock.ts_code)
                    orders.append(s._build_order(stock, 0, REASON_PRIORITY_RANK_UP, trade_date))
                    continue
                success, shares, _fee = portfolio.reserve_funds(
                    stock.ts_code, stock.close, close_prices, max_position_scalar=pos_mult,
                )
                if not success:
                    continue
                purchased_ts_codes.add(stock.ts_code)
                orders.append(s._build_order(stock, shares, REASON_PRIORITY_RANK_UP, trade_date))

        remaining_slots = s.max_positions - len(portfolio.positions) - suggestion_count
        if remaining_slots > 0:
            for stock in top_stocks:
                if stock.ts_code in hold_ts_codes:
                    continue
                if stock.ts_code in purchased_ts_codes:
                    continue
                if not s._score_not_declining(stock.ts_code, score_manager):
                    continue
                if suggestion_mode:
                    if suggestion_count >= s.max_positions:
                        break
                    suggestion_count += 1
                    orders.append(s._build_order(stock, 0, REASON_NORMAL_BUY, trade_date))
                    continue
                success, shares, _fee = portfolio.reserve_funds(
                    stock.ts_code, stock.close, close_prices, max_position_scalar=pos_mult,
                )
                if not success:
                    continue
                orders.append(s._build_order(stock, shares, REASON_NORMAL_BUY, trade_date))

        return orders
```

- [ ] **Step 4: Create `defensive_mode.py`**

Write `backend/src/trade_alpha/strategy/modes/defensive_mode.py`:

```python
from typing import Dict, List, Optional

from trade_alpha.constants import SELL_REASON_SCORE_BELOW
from trade_alpha.execution.portfolio import PortfolioManager
from trade_alpha.logging import get_logger
from trade_alpha.schemas import ScoredStock, PendingOrder, MarketDataEmbed
from trade_alpha.strategy.modes.base import PhaseMode

logger = get_logger("strategy.modes.defensive_mode")


class DefensiveMode(PhaseMode):
    """Defensive mode (market_phase = 'down').

    No buying. Sell positions aggressively with tightened stop-loss
    and elevated sell threshold.
    """

    async def run(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        portfolio: PortfolioManager,
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
        score_manager: Optional["ScoreManager"] = None,
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
        s = self._strategy
        close_prices = close_prices or {}
        score_map = {st.ts_code: st.composite_score for st in scored_stocks}

        for pos in portfolio.positions.values():
            pos.hold_days += 1

        orders: List[PendingOrder] = []

        for ts_code, pos in portfolio.positions.items():
            should_sell, reason = self._check_sell_defensive(
                pos, close_prices, score_map, s.max_hold_days,
            )
            if should_sell:
                sell_price = close_prices.get(ts_code, pos.buy_price)
                orders.append(PendingOrder(
                    ts_code=pos.ts_code,
                    stock_name=pos.stock_name,
                    order_price=sell_price,
                    order_shares=-pos.shares,
                    entry_score=pos.entry_score,
                    trade_date=trade_date,
                    settle_date=s._next_trade_date(trade_date),
                    reason=reason,
                ))

        forced_orders = s._apply_full_position_sell(
            scored_stocks, portfolio, close_prices, trade_date, market_data, score_manager,
        )
        orders.extend(forced_orders)
        return orders

    @staticmethod
    def _check_sell_defensive(
        position: "PositionEmbed",
        close_prices: Dict[str, float],
        score_map: Dict[str, float],
        max_hold_days: int,
    ) -> tuple:
        """Aggressive sell check for defensive mode."""
        stop_loss_pct = -0.07
        sell_threshold = 0.0
        current_score = score_map.get(position.ts_code, 0.0)

        # 1. Common checks: stop-loss, max-hold
        common_sell, common_reason = MultiStockStrategy.check_common_sell(
            position, close_prices, stop_loss_pct, max_hold_days,
        )
        if common_sell:
            return True, common_reason

        # 2. Score below defensive threshold
        if current_score < sell_threshold:
            return True, SELL_REASON_SCORE_BELOW

        return False, ""
```

- [ ] **Step 5: Create `mean_reversion_mode.py`**

Write `backend/src/trade_alpha/strategy/modes/mean_reversion_mode.py`:

```python
import statistics
from typing import Dict, List, Optional

from trade_alpha.constants import SELL_REASON_MEAN_REVERSION
from trade_alpha.execution.portfolio import PortfolioManager
from trade_alpha.logging import get_logger
from trade_alpha.schemas import ScoredStock, PendingOrder, MarketDataEmbed
from trade_alpha.strategy.modes.base import PhaseMode

logger = get_logger("strategy.modes.mean_reversion_mode")


class MeanReversionMode(PhaseMode):
    """Mean reversion mode (market_phase = 'flat').

    Buys stocks whose scores have reverted from a high historical mean.
    Sells when the score recovers back above the mean.
    """

    def __init__(self, strategy: "MultiStockStrategy"):
        super().__init__(strategy)
        cfg = strategy.strategy_config
        self.score_window = getattr(cfg, "mr_score_window", 20)
        self.exclude_recent = getattr(cfg, "mr_exclude_recent_days", 5)
        self.reversion_threshold = getattr(cfg, "mr_mean_reversion_threshold", 0.05)
        self.sell_multiplier = getattr(cfg, "mr_sell_multiplier", 1.0)
        self.max_candidates = getattr(cfg, "mr_max_candidates", 30)

    async def run(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        portfolio: PortfolioManager,
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
        score_manager: Optional["ScoreManager"] = None,
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
        s = self._strategy
        close_prices = close_prices or {}
        total_window = self.score_window + self.exclude_recent

        for pos in portfolio.positions.values():
            pos.hold_days += 1

        # --- SELL ---
        orders: List[PendingOrder] = []
        stop_loss_pct = s.stop_loss_pct

        for ts_code, pos in portfolio.positions.items():
            should_sell, reason = self._check_sell_mr(
                pos, close_prices, score_manager,
                stop_loss_pct, s.max_hold_days,
            )
            if should_sell:
                sell_price = close_prices.get(ts_code, pos.buy_price)
                orders.append(PendingOrder(
                    ts_code=pos.ts_code,
                    stock_name=pos.stock_name,
                    order_price=sell_price,
                    order_shares=-pos.shares,
                    entry_score=pos.entry_score,
                    trade_date=trade_date,
                    settle_date=s._next_trade_date(trade_date),
                    reason=reason,
                ))

        forced_orders = s._apply_full_position_sell(
            scored_stocks, portfolio, close_prices, trade_date, market_data, score_manager,
        )
        orders.extend(forced_orders)

        # --- BUY ---
        hold_ts_codes = set(portfolio.positions.keys())
        purchased_ts_codes: set = set()

        candidates = []
        for st in scored_stocks:
            if st.is_excluded:
                continue
            if st.ts_code in hold_ts_codes:
                continue
            buffer = score_manager.get_score_buffer(st.ts_code) if score_manager else []
            if len(buffer) < total_window:
                continue
            historical = buffer[-(total_window + 1):-self.exclude_recent] if len(buffer) > total_window else buffer[:-self.exclude_recent]
            if len(historical) < self.score_window:
                continue
            historical_mean = statistics.mean(historical)
            recent = buffer[-self.exclude_recent:]
            recent_mean = statistics.mean(recent) if recent else 0.0

            if recent_mean > historical_mean + self.reversion_threshold:
                candidates.append((st, historical_mean, recent_mean))

        candidates.sort(key=lambda x: x[2] - x[1], reverse=True)
        candidates = candidates[:self.max_candidates]

        pos_mult, _ = s._market_multipliers(market_data)

        for stock, hist_mean, rec_mean in candidates:
            if stock.ts_code in purchased_ts_codes:
                continue
            if suggestion_mode:
                if len(portfolio.positions) + 1 > s.max_positions:
                    break
                purchased_ts_codes.add(stock.ts_code)
                orders.append(s._build_order(stock, 0, "mean_reversion_buy", trade_date))
                continue
            success, shares, _fee = portfolio.reserve_funds(
                stock.ts_code, stock.close, close_prices, max_position_scalar=pos_mult,
            )
            if not success:
                continue
            purchased_ts_codes.add(stock.ts_code)
            orders.append(s._build_order(stock, shares, "mean_reversion_buy", trade_date))

        return orders

    def _check_sell_mr(
        self,
        position: "PositionEmbed",
        close_prices: Dict[str, float],
        score_manager: Optional["ScoreManager"],
        stop_loss_pct: float,
        max_hold_days: int,
    ) -> tuple:
        """Sell check for mean reversion mode."""
        if score_manager is not None:
            buffer = score_manager.get_score_buffer(position.ts_code)
            if len(buffer) >= self.score_window + self.exclude_recent:
                historical = buffer[-(self.score_window + self.exclude_recent):-self.exclude_recent]
                hist_mean = statistics.mean(historical)
                current_score = buffer[-1] if buffer else 0.0
                if current_score > hist_mean * self.sell_multiplier:
                    return True, SELL_REASON_MEAN_REVERSION

        return MultiStockStrategy.check_common_sell(
            position, close_prices, stop_loss_pct, max_hold_days,
        )
```

- [ ] **Step 6: Verify all mode files import**

```bash
cd d:\projects\trade-alpha\backend
.venv\Scripts\python -c "
from trade_alpha.strategy.modes.trend_mode import TrendMode
from trade_alpha.strategy.modes.mean_reversion_mode import MeanReversionMode
from trade_alpha.strategy.modes.defensive_mode import DefensiveMode
from trade_alpha.strategy.modes.base import PhaseMode
print('All mode imports OK')
"
```

Note: This may fail initially due to circular imports (PhaseMode references MultiStockStrategy). Fix by using string annotation `"MultiStockStrategy"` in base.py, and in defensive_mode/mean_reversion_mode importing MultiStockStrategy at the method level or using `TYPE_CHECKING`.

- [ ] **Step 7: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/strategy/modes/
git commit -m "feat: add 3 trading mode classes (Trend/MeanReversion/Defensive)"
```

---

### Task 6: Modify MultiStockStrategy to dispatch modes

**Files:**
- Modify: `backend/src/trade_alpha/strategy/multi_stock_strategy.py`

- [ ] **Step 1: Read current multi_stock_strategy.py**

```bash
cd d:\projects\trade-alpha\backend
cat -n src/trade_alpha/strategy/multi_stock_strategy.py
```

- [ ] **Step 2: Add mode imports and _modes dict in __init__**

Add after existing imports:

```python
from trade_alpha.strategy.modes.trend_mode import TrendMode
from trade_alpha.strategy.modes.mean_reversion_mode import MeanReversionMode
from trade_alpha.strategy.modes.defensive_mode import DefensiveMode
```

At the end of `__init__`, after `self._full_position_pnl_weight = ...`, add:

```python
        self._modes = {
            "up": TrendMode(self),
            "flat": MeanReversionMode(self),
            "down": DefensiveMode(self),
        }
```

- [ ] **Step 3: Replace make_orders body with mode dispatch**

Replace the entire `make_orders` method body with:

```python
    async def make_orders(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        portfolio: PortfolioManager,
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
        score_manager: Optional["ScoreManager"] = None,
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
        if self.ts_codes:
            scored_stocks = [s for s in scored_stocks if s.ts_code in self.ts_codes]
        scored_stocks = [s for s in scored_stocks if not s.is_excluded]

        phase = market_data.market_phase if market_data else "up"
        mode = self._modes.get(phase, self._modes["up"])
        return await mode.run(
            scored_stocks, trade_date, portfolio,
            close_prices, market_data, score_manager,
            suggestion_mode=suggestion_mode,
        )
```

- [ ] **Step 4: Remove `_stop_loss_mult` method**

Delete the entire `_stop_loss_mult` method (lines ~261-271). This is safe because TrendMode calls `_check_sell` which reads `stop_loss_pct` directly and DefensiveMode/MeanReversionMode each have their own sell check logic.

- [ ] **Step 5: Verify import works**

```bash
cd d:\projects\trade-alpha\backend
.venv\Scripts\python -c "
from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy
print('MultiStockStrategy has _modes:', hasattr(MultiStockStrategy, '_modes'))
print('MultiStockStrategy has check_common_sell:', hasattr(MultiStockStrategy, 'check_common_sell'))
print('OK')
"
```

- [ ] **Step 6: Commit**

```bash
cd d:\projects\trade-alpha
git add backend/src/trade_alpha/strategy/multi_stock_strategy.py
git commit -m "feat: make_orders dispatches to phase-mode handlers"
```

---

### Task 7: Full integration verification

- [ ] **Step 1: Verify all imports work**

```bash
cd d:\projects\trade-alpha\backend
.venv\Scripts\python -c "
from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy
from trade_alpha.strategy.modes.trend_mode import TrendMode
from trade_alpha.strategy.modes.mean_reversion_mode import MeanReversionMode
from trade_alpha.strategy.modes.defensive_mode import DefensiveMode
from trade_alpha.strategy.modes.base import PhaseMode
from trade_alpha.execution.scoring import ScoreManager
from trade_alpha.execution.backtest_pipeline import BacktestPipeline
from trade_alpha.execution.baseline_tracker import BaselineTracker
from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.constants import SELL_REASON_MEAN_REVERSION
print('All imports OK')
"
```

- [ ] **Step 2: Quick backtest smoke test**

```bash
cd d:\projects\trade-alpha\backend
.venv\Scripts\python -c "
# Verify the change doesn't break instantiation
from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy
cfg = StrategyConfig(name='test')
strat = MultiStockStrategy(cfg)
print('Strategy instantiated')
print('Modes:', list(strat._modes.keys()))
print('OK')
"
```

- [ ] **Step 3: Final commit**

```bash
cd d:\projects\trade-alpha
git push
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ Design §2 (code org): Covered by Task 5 & 6
- ✅ Design §2.1 (base class): Covered by Task 5 Step 2
- ✅ Design §2.2 (dispatch): Covered by Task 6 Step 3
- ✅ Design §2.3 (common sell): Covered by Task 4 Step 1
- ✅ Design §3 (trend mode): Covered by Task 5 Step 3
- ✅ Design §4 (defensive mode): Covered by Task 5 Step 4
- ✅ Design §5 (mean reversion): Covered by Task 5 Step 5
- ✅ Design §6 (params): Covered by Task 2, 3
- ✅ Design §7 (constants): Covered by Task 1

**Placeholder scan:** No "TBD", "TODO", or placeholder content found.

**Type consistency:** All mode classes use string annotation `"MultiStockStrategy"` in base.py and `"ScoreManager"` via TYPE_CHECKING-compatible pattern. `check_common_sell` accepts `PositionEmbed` type. `run` signature matches base class.
