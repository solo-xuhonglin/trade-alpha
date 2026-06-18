# Strategy-Mode Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple modes from strategy (remove back-reference) and move common order flow into `MultiStockStrategy.make_orders()`, with modes becoming pure stateless stock selectors.

**Architecture:** `PhaseMode` becomes stateless with a single method `select_buy_candidates()`. `MultiStockStrategy.make_orders()` owns the full flow (sell loop, full_position_sell, buy processing) and calls the mode only for buy candidate selection. Mode param overrides (RotationMode's different min_hold_days, sell_threshold) are class-level constants read via `_apply_mode_params()`. Modes are created without strategy reference and stored in `PipelineContext.mode_map`.

**Tech Stack:** Python 3.14+, async/await, Beanie ODM, Pydantic

---

### Task 1: Add BuyCandidate to schemas.py

**Files:**
- Modify: `backend/src/trade_alpha/schemas.py:1-6` (add import + dataclass)

- [ ] **Step 1: Add BuyCandidate dataclass**

Add after `MarketDataEmbed` class (line 101), before any other unrelated code:

```python
from dataclasses import dataclass


@dataclass
class BuyCandidate:
    """A stock recommended by the mode for purchase, with buy reason."""
    stock: ScoredStock
    reason: str = ""
```

Note: `dataclass` is used (not Pydantic) because this is an ephemeral internal structure, not persisted or validated.

- [ ] **Step 2: Verify import**

Run: `python -c "from trade_alpha.schemas import BuyCandidate; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/schemas.py
git commit -m "feat: add BuyCandidate dataclass for mode stock selection"
```

---

### Task 2: Rewrite PhaseMode base as stateless selector

**Files:**
- Modify: `backend/src/trade_alpha/strategy/modes/base.py` (full rewrite)

- [ ] **Step 1: Write new PhaseMode base**

Replace entire file content:

```python
from abc import ABC, abstractmethod
from typing import List, Optional

from trade_alpha.schemas import ScoredStock, BuyCandidate, MarketDataEmbed
from trade_alpha.execution.context import PipelineContext


class PhaseMode(ABC):
    """Stateless stock selector. No strategy back-reference.

    Each mode only answers: which stocks should we buy today?
    The strategy owns the full order flow (sell, full_position_sell, buy processing).
    """

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
        """Return buy candidates sorted by priority (highest first).

        The strategy will iterate candidates in order, skip already-held
        or already-purchased stocks, and process remaining via
        reserve_funds + _build_order.
        """
```

- [ ] **Step 2: Verify import**

Run: `python -c "from trade_alpha.strategy.modes.base import PhaseMode; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/strategy/modes/base.py
git commit -m "refactor: rewrite PhaseMode as stateless selector without strategy ref"
```

---

### Task 3: Rewrite TrendMode with select_buy_candidates only

**Files:**
- Modify: `backend/src/trade_alpha/strategy/modes/trend_mode.py` (full rewrite)

- [ ] **Step 1: Write new TrendMode**

Replace entire file content:

```python
from typing import List, Optional, Set

from trade_alpha.constants import REASON_NORMAL_BUY, REASON_PRIORITY_RANK_UP
from trade_alpha.logging import get_logger
from trade_alpha.schemas import ScoredStock, BuyCandidate, MarketDataEmbed
from trade_alpha.strategy.modes.base import PhaseMode
from trade_alpha.execution.context import PipelineContext

logger = get_logger("strategy.modes.trend_mode")


class TrendMode(PhaseMode):
    """Trend-following mode (market_phase = 'up').

    Selects top-ranked stocks above score threshold.
    Prioritizes rank-improving stocks, then fills remaining from top stocks.
    """

    def select_buy_candidates(
        self,
        scored_stocks: List[ScoredStock],
        ctx: PipelineContext,
        market_data: Optional[MarketDataEmbed] = None,
    ) -> List[BuyCandidate]:
        config = ctx.strategy_config

        # Compute effective multipliers
        pos_mult = 1.0
        buy_mult = 1.0
        if getattr(config, "use_phase_strategy", True) and market_data is not None:
            pos_mult = market_data.position_multiplier
            buy_mult = market_data.buy_threshold_multiplier

        effective_threshold = config.buy_threshold * buy_mult
        effective_max = max(1, int(config.max_positions * pos_mult))

        # Full candidates (before score filter) — for rank_up check
        full_candidates = sorted(scored_stocks, key=lambda s: s.ranking_score, reverse=True)

        # Score-filtered candidates
        above = [s for s in scored_stocks if s.composite_score > effective_threshold]
        sorted_above = sorted(above, key=lambda s: s.ranking_score, reverse=True)

        if len(sorted_above) <= 5:
            logger.info(f"select_buy_candidates scored_above_threshold={len(sorted_above)}")
        elif len(sorted_above) % 10 == 0:
            logger.info(f"select_buy_candidates scored_above_threshold={len(sorted_above)}")

        top_stocks = sorted_above[:effective_max]

        candidates: List[BuyCandidate] = []
        purchased: Set[str] = set()
        hold_ts_codes = set(ctx.portfolio.positions.keys())

        # --- Rank-up priority ---
        if config.use_rank_up_priority and config.rank_up_count > 0:
            rank_up_list = [
                s for s in full_candidates
                if s.ts_code not in hold_ts_codes
                and s.rank_improvement >= config.rank_up_min_improvement_pct
                and s.composite_score > config.rank_up_min_score * buy_mult
            ]
            # Filter by score_not_declining
            rank_up_list = [
                s for s in rank_up_list
                if _score_not_declining(s.ts_code, config, ctx)
            ]
            rank_up_list.sort(key=lambda s: s.rank_improvement, reverse=True)
            for s in rank_up_list[:config.rank_up_count]:
                purchased.add(s.ts_code)
                candidates.append(BuyCandidate(stock=s, reason=REASON_PRIORITY_RANK_UP))

        # --- Remaining from top_stocks ---
        for s in top_stocks:
            if s.ts_code in purchased or s.ts_code in hold_ts_codes:
                continue
            if not _score_not_declining(s.ts_code, config, ctx):
                continue
            candidates.append(BuyCandidate(stock=s, reason=REASON_NORMAL_BUY))

        return candidates


def _score_not_declining(ts_code: str, config, ctx: PipelineContext) -> bool:
    """Check if stock's composite_score isn't dropping significantly.

    Standalone function shared between TrendMode and MultiStockStrategy.
    Uses raw score buffer for day-over-day comparison with threshold.
    """
    if not config.use_score_decline_filter:
        return True
    buffer = ctx.score_manager.get_score_buffer(ts_code)
    return len(buffer) < 2 or buffer[-1] >= buffer[-2] - config.score_decline_threshold
```

Note: `_score_not_declining` is extracted as a module-level function so both `TrendMode` and `MultiStockStrategy._apply_full_position_sell` can use it. MultiStockStrategy's method will be updated to delegate to this function in Task 6.

- [ ] **Step 2: Verify import**

Run: `python -c "from trade_alpha.strategy.modes.trend_mode import TrendMode; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/strategy/modes/trend_mode.py
git commit -m "refactor: rewrite TrendMode as stateless stock selector"
```

---

### Task 4: Rewrite RotationMode with select_buy_candidates only

**Files:**
- Modify: `backend/src/trade_alpha/strategy/modes/rotation_mode.py` (full rewrite)

- [ ] **Step 1: Write new RotationMode**

Replace entire file content:

```python
from typing import List, Optional

from trade_alpha.logging import get_logger
from trade_alpha.schemas import ScoredStock, BuyCandidate, MarketDataEmbed
from trade_alpha.strategy.modes.base import PhaseMode
from trade_alpha.execution.context import PipelineContext

logger = get_logger("strategy.modes.rotation_mode")


class RotationMode(PhaseMode):
    """Rotation trading mode for flat + down market phases.

    Buys stocks showing ranking rotation: once top-ranked, fallen to
    bottom, now at potential reversal zone (rank 50-70).

    Overrides strategy defaults for tighter sell discipline:
    - min_hold_days=10: longer holding period for mean-reversion plays
    - sell_threshold=-0.5: more tolerant of score decline
    """

    min_hold_days = 10
    sell_threshold = -0.5
    full_position_score_window = 10

    def select_buy_candidates(
        self,
        scored_stocks: List[ScoredStock],
        ctx: PipelineContext,
        market_data: Optional[MarketDataEmbed] = None,
    ) -> List[BuyCandidate]:
        config = ctx.strategy_config
        score_manager = ctx.score_manager
        hold_ts_codes = set(ctx.portfolio.positions.keys())

        candidates: List[BuyCandidate] = []

        for st in scored_stocks:
            if st.is_excluded:
                continue
            if st.ts_code in hold_ts_codes:
                continue
            if not (config.rotation_rank_min <= st.rank <= config.rotation_rank_max):
                continue

            rank_history = score_manager.get_rank_history(st.ts_code) if score_manager else []
            if len(rank_history) < 6:
                continue
            was_top = any(r <= config.rotation_was_top_n for r in rank_history[:-5])
            recent_bottom = any(r >= config.rotation_bottom_threshold for r in rank_history[-5:])
            if not (was_top and recent_bottom):
                continue
            # Reversal check: today's rank should be better than recent 5-day average
            if config.rotation_use_reversal_check:
                avg_rank_5d = sum(rank_history[-6:-1]) / 5
                if st.rank >= avg_rank_5d:
                    continue
            candidates.append(BuyCandidate(stock=st, reason="rotation_buy"))

        candidates.sort(key=lambda c: c.stock.rank)
        logger.info(f"select_buy_candidates rotation_candidates={len(candidates)}")
        return candidates
```

- [ ] **Step 2: Verify import**

Run: `python -c "from trade_alpha.strategy.modes.rotation_mode import RotationMode; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/trade_alpha/strategy/modes/rotation_mode.py
git commit -m "refactor: rewrite RotationMode as stateless stock selector"
```

---

### Task 5: Add mode_map to PipelineContext and update callers

**Files:**
- Modify: `backend/src/trade_alpha/execution/context.py:21-37` (add mode_map param)
- Modify: `backend/src/trade_alpha/execution/suggestion_pipeline.py:73-80` (pass mode_map)
- Modify: `backend/src/trade_alpha/execution/backtest_pipeline.py:83-91` (pass mode_map)

- [ ] **Step 1: Add mode_map to PipelineContext**

Edit [context.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/execution/context.py):

Add import at top:
```python
from typing import Any, Dict, Optional
from trade_alpha.strategy.modes.base import PhaseMode
```

Add `mode_map` parameter to `__init__`:
```python
    def __init__(
        self,
        data_loader: DataLoader,
        score_manager: ScoreManager,
        portfolio: PortfolioManager,
        strategy_config: StrategyConfig,
        model_config: ModelConfig,
        predictor: Any = None,
        account_config: Optional[AccountConfig] = None,
        mode_map: Optional[Dict[str, PhaseMode]] = None,
    ):
        self.data_loader = data_loader
        self.score_manager = score_manager
        self.portfolio = portfolio
        self.predictor = predictor
        self.strategy_config = strategy_config
        self.model_config = model_config
        self.account_config = account_config
        self.mode_map = mode_map or {}
```

- [ ] **Step 2: Update suggestion_pipeline.py**

Edit [suggestion_pipeline.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/execution/suggestion_pipeline.py):

Add imports at top:
```python
from trade_alpha.strategy.modes.trend_mode import TrendMode
from trade_alpha.strategy.modes.rotation_mode import RotationMode
```

Update PipelineContext construction (add mode_map):
```python
        self.ctx = PipelineContext(
            data_loader=self.data_loader,
            score_manager=self.score_manager,
            portfolio=self.portfolio,
            predictor=self.predictor,
            strategy_config=self.strategy_config,
            model_config=self.model_config,
            mode_map={
                "up": TrendMode(),
                "flat": RotationMode(),
                "down": RotationMode(),
            },
        )
```

- [ ] **Step 3: Update backtest_pipeline.py**

Edit [backtest_pipeline.py](file:///d:/projects/trade-alpha/backend/src/trade_alpha/execution/backtest_pipeline.py):

Add imports at top:
```python
from trade_alpha.strategy.modes.trend_mode import TrendMode
from trade_alpha.strategy.modes.rotation_mode import RotationMode
```

Update PipelineContext construction (add mode_map):
```python
        self.ctx = PipelineContext(
            data_loader=self.data_loader,
            score_manager=self.score_manager,
            portfolio=self.portfolio,
            predictor=self.predictor,
            strategy_config=self.strategy_config,
            model_config=self.model_config,
            account_config=self.account_config,
            mode_map={
                "up": TrendMode(),
                "flat": RotationMode(),
                "down": RotationMode(),
            },
        )
```

- [ ] **Step 4: Verify imports**

Run: `python -c "from trade_alpha.execution.context import PipelineContext; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/src/trade_alpha/execution/context.py backend/src/trade_alpha/execution/suggestion_pipeline.py backend/src/trade_alpha/execution/backtest_pipeline.py
git commit -m "feat: add mode_map to PipelineContext"
```

---

### Task 6: Rewrite MultiStockStrategy — full flow in make_orders

**Files:**
- Modify: `backend/src/trade_alpha/strategy/multi_stock_strategy.py` (major changes)

This is the core task. Changes needed:
1. Remove `TrendMode`/`RotationMode` imports and `self._modes` creation
2. Add `_apply_mode_params(mode)` method
3. Expand `make_orders()` with the full sell+buy flow
4. Update `_score_not_declining` to delegate to the module-level function (or inline it)
5. Remove `TYPE_CHECKING` import for PortfolioManager (no longer needed since modes don't reference strategy)

- [ ] **Step 1: Rewrite MultiStockStrategy**

Replace entire file content:

```python
"""Multi-stock strategy - ranking-based multi-stock trading."""

from typing import List, Optional, Set, Tuple

from trade_alpha.constants import (
    SELL_REASON_FULL_POSITION,
    SELL_REASON_HOLD_SCORE_LOW,
    SELL_REASON_MAX_HOLD_DAYS,
    SELL_REASON_SCORE_BELOW,
    SELL_REASON_STOP_LOSS,
)
from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.schemas import ScoredStock, PendingOrder, MarketDataEmbed
from trade_alpha.strategy.base import BaseStrategy
from trade_alpha.strategy.modes.base import PhaseMode
from trade_alpha.logging import get_logger
from trade_alpha.execution.context import PipelineContext

logger = get_logger("strategy.multi_stock_strategy")


class MultiStockStrategy(BaseStrategy):
    """Multi-stock portfolio strategy based on ranking."""

    def __init__(
        self,
        strategy_config: StrategyConfig,
        ts_codes: Optional[List[str]] = None,
    ):
        super().__init__(
            buy_threshold=strategy_config.buy_threshold,
            sell_threshold=strategy_config.sell_threshold,
            min_order_value=strategy_config.min_order_value,
            stop_loss_pct=strategy_config.stop_loss_pct,
            min_hold_days=strategy_config.min_hold_days,
            max_hold_days=strategy_config.max_hold_days,
            max_positions=strategy_config.max_positions,
            max_position_pct=strategy_config.max_position_pct,
        )
        self.ts_codes = ts_codes or []
        self.strategy_config = strategy_config
        self._full_position_consecutive_days = 0
        self.full_position_score_window = strategy_config.full_position_score_window

    def _apply_mode_params(self, mode: PhaseMode) -> None:
        """Apply mode-specific parameter overrides."""
        self.min_hold_days = mode.min_hold_days or self.strategy_config.min_hold_days
        self.sell_threshold = mode.sell_threshold if mode.sell_threshold is not None else self.strategy_config.sell_threshold
        self.full_position_score_window = mode.full_position_score_window or self.strategy_config.full_position_score_window

    async def make_orders(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        ctx: PipelineContext,
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
        # ── 1. Filter scored_stocks ──
        if self.ts_codes:
            scored_stocks = [s for s in scored_stocks if s.ts_code in self.ts_codes]
        scored_stocks = [s for s in scored_stocks if not s.is_excluded]

        # ── 2. Select mode from context ──
        phase = market_data.market_phase if market_data else "up"
        mode = ctx.mode_map.get(phase, ctx.mode_map.get("up"))
        if mode is None:
            logger.warning(f"make_orders no mode found for phase={phase}, skip")
            return []

        # ── 3. Apply mode param overrides ──
        self._apply_mode_params(mode)

        # ── 4. Update peak prices (for trailing stop-loss) ──
        if close_prices:
            ctx.portfolio.update_peak_prices(close_prices)

        # ── 5. Build score_map + increment hold_days ──
        score_map = {st.ts_code: st.composite_score for st in scored_stocks}
        for pos in ctx.portfolio.positions.values():
            pos.hold_days += 1

        # ── 6. Compute sell_rank_ts_codes for check_sell ──
        pos_mult, _ = self._market_multipliers(market_data)
        sorted_all = sorted(scored_stocks, key=lambda s: s.ranking_score, reverse=True)
        top_n = max(1, int(self.max_positions * pos_mult))
        top_ts_codes = {s.ts_code for s in sorted_all[:top_n]}
        sell_rank_n = ctx.strategy_config.sell_rank_n
        sell_rank_ts_codes = {s.ts_code for s in sorted_all[:sell_rank_n]}

        # ── 7. Sell loop ──
        orders: List[PendingOrder] = []
        close_prices = close_prices or {}
        for ts_code, pos in ctx.portfolio.positions.items():
            should_sell, reason = self.check_sell(
                pos, top_ts_codes, sell_rank_ts_codes, score_map,
                close_prices, market_data, ctx=ctx,
            )
            if should_sell:
                in_score = ts_code in score_map
                in_sell_rank = ts_code in sell_rank_ts_codes
                current_score = score_map.get(ts_code, 0.0)
                logger.info(
                    f"make_orders SELL ts_code={ts_code} hold_days={pos.hold_days} "
                    f"in_score_map={in_score} current_score={current_score:.3f} "
                    f"in_sell_rank={in_sell_rank} reason={reason}"
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
                    settle_date=self._next_trade_date(trade_date),
                    reason=reason,
                ))

        # ── 8. Full position forced sell ──
        forced_orders = self._apply_full_position_sell(
            scored_stocks, close_prices, trade_date, ctx, market_data,
        )
        orders.extend(forced_orders)

        # ── 9. Get buy candidates from mode ──
        buy_candidates = mode.select_buy_candidates(scored_stocks, ctx, market_data)

        # ── 10. Process buy candidates ──
        hold_ts_codes: Set[str] = set(ctx.portfolio.positions.keys())
        purchased: Set[str] = set()
        suggestion_count = 0

        for cand in buy_candidates:
            if cand.stock.ts_code in hold_ts_codes or cand.stock.ts_code in purchased:
                continue
            if suggestion_mode:
                if suggestion_count >= self.max_positions:
                    break
                suggestion_count += 1
                orders.append(self._build_order(cand.stock, 0, cand.reason, trade_date))
                continue
            success, shares, _fee = ctx.portfolio.reserve_funds(
                cand.stock.ts_code, cand.stock.close, close_prices,
                max_position_scalar=pos_mult,
            )
            if not success:
                continue
            purchased.add(cand.stock.ts_code)
            orders.append(self._build_order(cand.stock, shares, cand.reason, trade_date))

        return orders

    def _build_order(
        self,
        stock: ScoredStock,
        order_shares: int,
        reason: str,
        trade_date: str,
    ) -> PendingOrder:
        """Build a PendingOrder from a ScoredStock."""
        return PendingOrder(
            ts_code=stock.ts_code,
            stock_name=stock.stock_name,
            order_price=stock.close,
            order_shares=order_shares,
            entry_score=stock.composite_score,
            up_prob_3d=stock.up_prob_3d,
            up_prob_5d=stock.up_prob_5d,
            up_prob_10d=stock.up_prob_10d,
            up_prob_20d=stock.up_prob_20d,
            trade_date=trade_date,
            settle_date=self._next_trade_date(trade_date),
            reason=reason,
        )

    def _market_multipliers(self, market_data: Optional[MarketDataEmbed] = None) -> Tuple[float, float]:
        if not getattr(self.strategy_config, "use_phase_strategy", True):
            return 1.0, 1.0
        if market_data is None:
            return 1.0, 1.0
        return (market_data.position_multiplier, market_data.buy_threshold_multiplier)

    _FULL_POSITION_PNL_CLIP_PCT = 50.0

    def _score_not_declining(self, ts_code: str, ctx: PipelineContext) -> bool:
        """Check if stock's composite_score isn't dropping significantly."""
        if not self.strategy_config.use_score_decline_filter:
            return True
        buffer = ctx.score_manager.get_score_buffer(ts_code)
        return len(buffer) < 2 or buffer[-1] >= buffer[-2] - self.strategy_config.score_decline_threshold

    def _apply_full_position_sell(
        self,
        scored_stocks: List[ScoredStock],
        close_prices: Dict[str, float],
        trade_date: str,
        ctx: PipelineContext,
        market_data: Optional[MarketDataEmbed] = None,
    ) -> List[PendingOrder]:
        """Sell worst-scored stocks when portfolio is over-positioned for N days."""
        forced_orders: List[PendingOrder] = []
        if not self.strategy_config or not getattr(self.strategy_config, "use_full_position_sell", False):
            return forced_orders
        threshold = getattr(self.strategy_config, "full_position_threshold", 0.90)
        pos_mult, _ = self._market_multipliers(market_data)
        threshold *= pos_mult
        days_required = getattr(self.strategy_config, "full_position_days", 3)
        score_window = self.full_position_score_window
        sell_count = getattr(self.strategy_config, "full_position_sell_count", 1)

        total_value = ctx.portfolio.get_total_value(close_prices)
        if total_value <= 0:
            return forced_orders
        cash = ctx.portfolio.cash
        market_value = total_value - cash
        invested_pct = market_value / total_value
        if invested_pct < threshold:
            self._full_position_consecutive_days = 0
            return forced_orders
        self._full_position_consecutive_days += 1
        if self._full_position_consecutive_days < days_required:
            return forced_orders

        if not ctx.portfolio.positions:
            return forced_orders

        # Build stock_name lookup from scored_stocks
        stock_name_map = {s.ts_code: s.stock_name for s in scored_stocks}

        scored_holds: List[tuple] = []
        for ts_code, pos in ctx.portfolio.positions.items():
            buffer = ctx.score_manager.get_score_buffer(ts_code) or []
            if len(buffer) >= score_window:
                avg_score = sum(buffer[-score_window:]) / score_window
            elif buffer:
                avg_score = sum(buffer) / len(buffer)
            else:
                avg_score = 0.0

            pnl_pct = 0.0
            if close_prices and ts_code in close_prices:
                cost_basis = (pos.buy_price * pos.shares + pos.fee) / pos.shares
                if cost_basis > 0:
                    pnl_pct = (close_prices[ts_code] - cost_basis) / cost_basis * 100

            pnl_clipped = max(min(pnl_pct, self._FULL_POSITION_PNL_CLIP_PCT), -self._FULL_POSITION_PNL_CLIP_PCT) / 100.0
            sell_priority = avg_score + pnl_clipped * self.strategy_config.full_position_pnl_weight
            scored_holds.append((sell_priority, avg_score, pnl_pct, ts_code))
            logger.debug(f"full_position FORCE_SELL CANDIDATE ts_code={ts_code} avg_score={avg_score:.3f} pnl={pnl_pct:+.1f}% priority={sell_priority:.3f}")

        logger.info(f"full_position FORCE_SELL trade_date={trade_date} candidates={len(scored_holds)} sell_count={sell_count}")

        scored_holds.sort(key=lambda x: x[0])
        for i in range(min(sell_count, len(scored_holds))):
            priority, avg_score, pnl_pct, ts_code = scored_holds[i]
            pos = ctx.portfolio.positions.get(ts_code)
            if not pos:
                continue
            logger.info(f"full_position FORCE_SELL SELL ts_code={ts_code} priority={priority:.3f} avg_score={avg_score:.3f} pnl={pnl_pct:+.1f}%")
            forced_orders.append(PendingOrder(
                ts_code=ts_code,
                stock_name=stock_name_map.get(ts_code, ts_code),
                order_price=close_prices.get(ts_code, 0),
                order_shares=-pos.shares,
                entry_score=0.0,
                trade_date=trade_date,
                settle_date=self._next_trade_date(trade_date),
                reason=SELL_REASON_FULL_POSITION,
            ))

        return forced_orders

    def check_sell(
        self,
        position: PositionEmbed,
        top_ts_codes: set,
        sell_rank_ts_codes: set,
        score_map: Dict[str, float],
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
        ctx: Optional[PipelineContext] = None,
    ) -> Tuple[bool, str]:
        """Check whether a position should be sold.

        Returns:
            Tuple of (should_sell: bool, reason: str).
        """
        current_score = score_map.get(position.ts_code, 0.0)
        vol_multiplier = market_data.baseline_vol_multiplier if market_data else 1.0
        portfolio = ctx.portfolio if ctx else None

        if position.hold_days < self.min_hold_days:
            if close_prices and portfolio and portfolio.is_stop_loss_triggered(
                position.ts_code, close_prices, self.stop_loss_pct, vol_multiplier,
            ):
                logger.debug(f"check_sell ts_code={position.ts_code} stop_loss triggered, sell")
                return True, SELL_REASON_STOP_LOSS
            logger.debug(f"check_sell ts_code={position.ts_code} hold_days < min_hold_days, skip sell")
            return False, ""

        if current_score < self.sell_threshold:
            logger.debug(f"check_sell ts_code={position.ts_code} score below sell_threshold={self.sell_threshold:.3f}, sell")
            return True, SELL_REASON_SCORE_BELOW

        if position.hold_days >= self.max_hold_days:
            logger.debug(f"check_sell ts_code={position.ts_code} max_hold_days={self.max_hold_days} reached, sell")
            return True, SELL_REASON_MAX_HOLD_DAYS

        if close_prices and portfolio and portfolio.is_stop_loss_triggered(
            position.ts_code, close_prices, self.stop_loss_pct, vol_multiplier,
        ):
            return True, SELL_REASON_STOP_LOSS

        if position.ts_code not in sell_rank_ts_codes:
            if current_score < self.strategy_config.hold_score_threshold:
                logger.debug(f"check_sell ts_code={position.ts_code} hold_score_low={self.strategy_config.hold_score_threshold:.3f}, sell")
                return True, SELL_REASON_HOLD_SCORE_LOW

        return False, ""
```

Key changes from current:
1. Removed `TrendMode`/`RotationMode` imports and `TYPE_CHECKING` import
2. Removed `self._modes` dict from `__init__`
3. Added `_apply_mode_params(mode)` method
4. `make_orders()` now reads `mode = ctx.mode_map[phase]` instead of `self._modes[phase]`
5. `make_orders()` expanded to include sell loop, full_position_sell, and buy processing
6. Removed `isinstance(mode, RotationMode)` check — replaced by `_apply_mode_params(mode)`
7. `_score_not_declining` kept as-is on the strategy (used by `_apply_full_position_sell`)

- [ ] **Step 2: Verify import**

Run: `python -c "from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Verify full module import chain**

Run: `python -c "from trade_alpha.execution.context import PipelineContext; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/src/trade_alpha/strategy/multi_stock_strategy.py
git commit -m "refactor: move full order flow into make_orders, remove mode back-refs"
```

---

### Task 7: Run integration tests

**Files:** No code changes — test execution only.

- [ ] **Step 1: Run full integration test suite**

Run:
```powershell
cd backend; .venv\Scripts\pytest tests\trade_alpha\integration\ -v 2>&1 | Select-Object -Last 20
```

Expected: All tests pass (126 passed).

If any tests fail:
1. Read the error output
2. Fix the issue in the relevant file
3. Re-run the failing test: `.venv\Scripts\pytest tests\trade_alpha\integration\test_XX_xxx.py -v`
4. Re-run full suite after fix

- [ ] **Step 2: Commit if any fixes were applied during testing**

```bash
git add -A
git commit -m "fix: resolve integration test issues after strategy-mode refactoring"
```

---

### Task 8: Clean up stale imports (if any)

Check if `TrendMode`/`RotationMode` are imported anywhere they're no longer needed.

- [ ] **Step 1: Search for stale TrendMode/RotationMode imports**

Run:
```powershell
Select-String -Path "backend/src/trade_alpha/strategy/multi_stock_strategy.py" -Pattern "trend_mode|rotation_mode"
```

Expected: No matches (imports were removed in Task 6).

- [ ] **Step 2: Check modes/__init__.py still imports cleanly**

Run: `python -c "from trade_alpha.strategy.modes import PhaseMode; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit if cleanup needed**

```bash
git add -A
git commit -m "chore: remove stale imports after strategy-mode refactoring"
```