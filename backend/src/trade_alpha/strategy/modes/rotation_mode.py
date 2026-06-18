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


logger = get_logger("strategy.modes.rotation_mode")


class RotationMode(PhaseMode):
    """Rotation trading mode for flat + down market phases.

    Buys stocks showing ranking rotation: once top-ranked, fallen to
    bottom, now at potential reversal zone (rank 50-70).
    """

    def __init__(self, strategy: "MultiStockStrategy"):
        super().__init__(strategy)

    async def settle_mode_orders(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        ctx: PipelineContext,
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
        suggestion_mode: bool = False,
        vol_multiplier: float = 1.0,
    ) -> List[PendingOrder]:
        close_prices = close_prices or {}
        score_map = {st.ts_code: st.composite_score for st in scored_stocks}
        portfolio = ctx.portfolio
        score_manager = ctx.score_manager

        for pos in portfolio.positions.values():
            pos.hold_days += 1

        # --- SELL ---
        orders: List[PendingOrder] = []

        for ts_code, pos in portfolio.positions.items():
            should_sell, reason = self._check_sell(pos, close_prices, score_map, portfolio, vol_multiplier)
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
            scored_stocks, close_prices, trade_date, ctx, market_data,
        )
        orders.extend(forced_orders)

        # --- BUY (ranking rotation signal) ---
        hold_ts_codes = set(portfolio.positions.keys())
        purchased_ts_codes: Set[str] = set()

        candidates = []
        config = self._strategy.strategy_config
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
                recent_ranks = rank_history[-6:-1]
                avg_rank_5d = sum(recent_ranks) / len(recent_ranks)
                if st.rank >= avg_rank_5d:
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
        portfolio: "PortfolioManager",
        vol_multiplier: float = 1.0,
    ) -> Tuple[bool, str]:
        """Sell check for rotation mode: stop_loss -> min_hold -> score -> max_hold."""
        strategy = self._strategy

        if portfolio.is_stop_loss_triggered(
            position.ts_code, close_prices, strategy.stop_loss_pct, vol_multiplier,
        ):
            return True, SELL_REASON_STOP_LOSS

        if position.hold_days < strategy.min_hold_days:
            return False, ""

        score = score_map.get(position.ts_code, 0.0)
        if score < strategy.sell_threshold:
            return True, SELL_REASON_SCORE_BELOW

        if position.hold_days >= strategy.max_hold_days:
            return True, SELL_REASON_MAX_HOLD_DAYS

        return False, ""
