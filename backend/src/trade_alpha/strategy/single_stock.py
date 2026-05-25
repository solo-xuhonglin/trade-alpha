"""Single-stock strategy - probability-based trading."""

from typing import Dict, List, Optional

from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.schemas import ScoredStock, PendingOrder
from trade_alpha.strategy.base import PositionManager
from trade_alpha.logging import get_logger

logger = get_logger("strategy.single_stock")


class SingleStockStrategy(PositionManager):
    """Single-stock strategy based on prediction probabilities."""

    def __init__(
        self,
        account_config: AccountConfig,
        target_ts_code: str,
        min_order_value: float = 5000,
        stop_loss_pct: float = -0.1,
        max_hold_days: int = 30,
    ):
        super().__init__(
            account_config=account_config,
            max_positions=1,
            max_position_pct=0.95,
            min_order_value=min_order_value,
            stop_loss_pct=stop_loss_pct,
            max_hold_days=max_hold_days,
        )
        self.target_ts_code = target_ts_code

    async def make_decisions(
        self,
        scored_stocks: List[ScoredStock],
        current_positions: Dict[str, PositionEmbed],
        cash: float,
        trade_date: str,
        close_prices: Optional[Dict[str, float]] = None,
    ) -> List[PendingOrder]:
        """Make decisions based on prediction probabilities."""
        target_stock = next((s for s in scored_stocks if s.ts_code == self.target_ts_code), None)
        if not target_stock:
            return []

        logger.debug(f"{trade_date} - {self.target_ts_code}: up_prob_3d={target_stock.up_prob_3d:.3f}, up_prob_5d={target_stock.up_prob_5d:.3f}, score={target_stock.score:.3f}")

        orders: List[PendingOrder] = []
        cash_available = cash
        current_position = current_positions.get(self.target_ts_code)

        if current_position:
            if self._should_sell(target_stock, current_position, close_prices):
                logger.debug(f"{trade_date} - Selling {self.target_ts_code}")
                sell_price = close_prices.get(self.target_ts_code, current_position.buy_price) if close_prices else current_position.buy_price
                sell_value = sell_price * current_position.shares
                sell_fee = max(sell_value * self.account_config.sell_fee_rate, self.account_config.min_fee)
                stamp_tax = sell_value * self.account_config.stamp_tax_rate
                cash_available += sell_value - sell_fee - stamp_tax
                orders.append(PendingOrder(
                    ts_code=current_position.ts_code,
                    stock_name=current_position.stock_name,
                    order_price=sell_price,
                    order_shares=-current_position.shares,
                    score=current_position.entry_score,
                    up_prob_3d=current_position.entry_3d_prob,
                    up_prob_5d=current_position.entry_5d_prob,
                    trade_date=trade_date,
                    settle_date=self._next_trade_date(trade_date),
                ))
                current_position = None

        if not current_position and self._should_buy(target_stock):
            logger.debug(f"{trade_date} - Buying {self.target_ts_code}")
            buy_order = self._allocate_buy(cash_available, target_stock, trade_date)
            if buy_order is not None:
                orders.append(buy_order)

        return orders

    def _should_buy(self, scored_stock: ScoredStock) -> bool:
        """Determine if we should buy based on score and threshold."""
        return scored_stock.score > self.buy_threshold

    def _should_sell(
        self,
        scored_stock: ScoredStock,
        position: PositionEmbed,
        close_prices: Optional[Dict[str, float]] = None,
    ) -> bool:
        """Determine if we should sell."""
        if scored_stock.score < self.sell_threshold:
            return True
        if position.hold_days >= self.max_hold_days:
            return True
        if close_prices and position.ts_code in close_prices:
            current_price = close_prices[position.ts_code]
            if current_price < position.buy_price * (1 + self.stop_loss_pct):
                return True
        return False

    def _allocate_buy(
        self,
        cash: float,
        scored_stock: ScoredStock,
        trade_date: str,
    ) -> Optional[PendingOrder]:
        """Allocate cash to buy a stock (higher position size)."""
        max_cost = cash * self.max_position_pct
        if max_cost < self.min_order_value:
            return None

        fee_rate = self.account_config.buy_fee_rate
        price = scored_stock.close
        if price <= 0:
            return None

        shares = int(max_cost / (price * (1 + fee_rate)) / 100) * 100
        if shares < 100:
            shares = 100

        total_cost = shares * price
        fee = max(total_cost * fee_rate, self.account_config.min_fee)
        if total_cost + fee > cash:
            shares = int((cash - self.account_config.min_fee) / price / 100) * 100
            if shares < 100:
                return None
            total_cost = shares * price
            fee = max(total_cost * fee_rate, self.account_config.min_fee)
            if total_cost + fee > cash:
                return None

        return PendingOrder(
            ts_code=scored_stock.ts_code,
            stock_name=scored_stock.stock_name,
            order_price=price,
            order_shares=shares,
            score=scored_stock.score,
            up_prob_3d=scored_stock.up_prob_3d,
            up_prob_5d=scored_stock.up_prob_5d,
            trade_date=trade_date,
            settle_date=self._next_trade_date(trade_date),
        )
