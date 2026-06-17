from typing import Dict, List, Optional, Tuple

from trade_alpha.constants import SELL_REASON_SCORE_BELOW
from trade_alpha.dao.position import PositionEmbed
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
        position: PositionEmbed,
        close_prices: Dict[str, float],
        score_map: Dict[str, float],
        max_hold_days: int,
    ) -> Tuple[bool, str]:
        """Aggressive sell check for defensive mode."""
        from trade_alpha.strategy.multi_stock_strategy import MultiStockStrategy
        stop_loss_pct = -0.07
        sell_threshold = 0.0
        current_score = score_map.get(position.ts_code, 0.0)

        common_sell, common_reason = MultiStockStrategy.check_common_sell(
            position, close_prices, stop_loss_pct, max_hold_days,
        )
        if common_sell:
            return True, common_reason

        if current_score < sell_threshold:
            return True, SELL_REASON_SCORE_BELOW

        return False, ""
