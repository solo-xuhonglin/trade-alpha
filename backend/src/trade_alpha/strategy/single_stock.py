"""Single-stock strategy - probability-based trading."""

from typing import Dict, List, Optional

from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.schemas import ScoredStock, PendingOrder, MarketDataEmbed
from trade_alpha.strategy.base import BaseStrategy
from trade_alpha.logging import get_logger
from trade_alpha.execution.context import PipelineContext

logger = get_logger("strategy.single_stock")


class SingleStockStrategy(BaseStrategy):
    """Single-stock strategy based on prediction probabilities."""

    def __init__(
        self,
        strategy_config: StrategyConfig,
        target_ts_code: str,
    ):
        super().__init__(
            max_positions=1,
            max_position_pct=0.95,
            min_order_value=strategy_config.min_order_value,
            stop_loss_pct=strategy_config.stop_loss_pct,
            max_hold_days=strategy_config.max_hold_days,
            buy_threshold=strategy_config.buy_threshold,
            sell_threshold=strategy_config.sell_threshold,
        )
        self.target_ts_code = target_ts_code

    async def make_orders(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        ctx: PipelineContext,
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
        suggestion_mode: bool = False,
    ) -> List[PendingOrder]:
        """Make decisions based on prediction probabilities.

        Uses ctx.portfolio.reserve_funds for buy feasibility.
        """
        target_stock = next((s for s in scored_stocks if s.ts_code == self.target_ts_code), None)
        if not target_stock:
            return []

        logger.debug(f"{trade_date} - {self.target_ts_code}: up_prob_3d={target_stock.up_prob_3d:.3f}, up_prob_5d={target_stock.up_prob_5d:.3f}, up_prob_10d={target_stock.up_prob_10d:.3f}, up_prob_20d={target_stock.up_prob_20d:.3f}, composite_score={target_stock.composite_score:.3f}")

        orders: List[PendingOrder] = []
        close_prices = close_prices or {}
        current_position = ctx.portfolio.positions.get(self.target_ts_code)

        if current_position:
            if self._should_sell(target_stock, current_position, close_prices):
                logger.debug(f"{trade_date} - Selling {self.target_ts_code}")
                sell_price = close_prices.get(self.target_ts_code, current_position.buy_price)
                orders.append(PendingOrder(
                    ts_code=current_position.ts_code,
                    stock_name=current_position.stock_name,
                    order_price=sell_price,
                    order_shares=-current_position.shares,
                    entry_score=current_position.entry_score,
                    up_prob_3d=current_position.entry_3d_prob,
                    up_prob_5d=current_position.entry_5d_prob,
                    up_prob_10d=current_position.entry_10d_prob,
                    up_prob_20d=current_position.entry_20d_prob,
                    trade_date=trade_date,
                    settle_date=self._next_trade_date(trade_date),
                ))
                return orders

        if not current_position and target_stock.composite_score > self.buy_threshold:
            logger.debug(f"{trade_date} - Buying {self.target_ts_code}")
            success, shares, _fee = ctx.portfolio.reserve_funds(
                self.target_ts_code, target_stock.close, close_prices,
            )
            if success:
                orders.append(PendingOrder(
                    ts_code=target_stock.ts_code,
                    stock_name=target_stock.stock_name,
                    order_price=target_stock.close,
                    order_shares=shares,
                    entry_score=target_stock.composite_score,
                    up_prob_3d=target_stock.up_prob_3d,
                    up_prob_5d=target_stock.up_prob_5d,
                    up_prob_10d=target_stock.up_prob_10d,
                    up_prob_20d=target_stock.up_prob_20d,
                    trade_date=trade_date,
                    settle_date=self._next_trade_date(trade_date),
                ))

        return orders

    def _should_buy(self, scored_stock: ScoredStock) -> bool:
        """Determine if we should buy based on composite_score and threshold."""
        return scored_stock.composite_score > self.buy_threshold

    def _should_sell(
        self,
        scored_stock: ScoredStock,
        position: PositionEmbed,
        close_prices: Optional[Dict[str, float]] = None,
    ) -> bool:
        """Determine if we should sell."""
        if scored_stock.composite_score < self.sell_threshold:
            return True
        if position.hold_days >= self.max_hold_days:
            return True
        if close_prices and position.ts_code in close_prices:
            current_price = close_prices[position.ts_code]
            if current_price < position.buy_price * (1 + self.stop_loss_pct):
                return True
        return False
