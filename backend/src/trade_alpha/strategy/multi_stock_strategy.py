"""Multi-stock strategy - ranking-based multi-stock trading."""

from typing import Dict, List, Optional, Set, Tuple

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