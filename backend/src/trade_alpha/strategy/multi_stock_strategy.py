"""Multi-stock strategy - ranking-based multi-stock trading."""

from typing import Dict, List, Optional

from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.schemas import ScoredStock, PendingOrder
from trade_alpha.strategy.base import PositionManager
from trade_alpha.logging import get_logger

logger = get_logger("strategy.multi_stock_strategy")


class MultiStockStrategy(PositionManager):
    """Multi-stock portfolio strategy based on ranking."""

    def __init__(
        self,
        account_config: AccountConfig,
        strategy_config: Optional[StrategyConfig],
        max_positions: int = 10,
        ts_codes: Optional[List[str]] = None,
    ):
        buy_threshold = strategy_config.buy_threshold if strategy_config else 0.1
        sell_threshold = strategy_config.sell_threshold if strategy_config else -0.1
        min_order_value = strategy_config.min_order_value if strategy_config else 5000.0
        stop_loss_pct = strategy_config.stop_loss_pct if strategy_config else -0.1
        max_hold_days = strategy_config.max_hold_days if strategy_config else 30
        cfg_max_positions = strategy_config.max_positions if strategy_config else 10
        max_position_pct = strategy_config.max_position_pct if strategy_config else 0.3
        sell_rank_n = strategy_config.sell_rank_n if strategy_config else 15
        hold_score_threshold = strategy_config.hold_score_threshold if strategy_config else 0.05

        super().__init__(
            account_config=account_config,
            max_positions=cfg_max_positions or max_positions,
            max_position_pct=max_position_pct or 0.3,
            min_order_value=min_order_value,
            stop_loss_pct=stop_loss_pct,
            max_hold_days=max_hold_days,
            buy_threshold=buy_threshold,
            sell_threshold=sell_threshold,
        )
        self.ts_codes = ts_codes or []
        self.sell_rank_n = sell_rank_n
        self.hold_score_threshold = hold_score_threshold

    async def make_decisions(
        self,
        scored_stocks: List[ScoredStock],
        current_positions: Dict[str, PositionEmbed],
        cash: float,
        trade_date: str,
        close_prices: Optional[Dict[str, float]] = None,
    ) -> List[PendingOrder]:
        """Make decisions based on ranking."""
        if self.ts_codes:
            scored_stocks = [s for s in scored_stocks if s.ts_code in self.ts_codes]

        scored_stocks = [s for s in scored_stocks if s.score > self.buy_threshold]
        scored_stocks = [s for s in scored_stocks if not s.is_excluded]
        sorted_stocks = sorted(scored_stocks, key=lambda s: s.score, reverse=True)
        
        top_stocks = sorted_stocks[:self.max_positions]
        top_ts_codes = {s.ts_code for s in top_stocks}
        
        sell_rank_stocks = sorted_stocks[:self.sell_rank_n]
        sell_rank_ts_codes = {s.ts_code for s in sell_rank_stocks}
        
        score_map = {s.ts_code: s.score for s in scored_stocks}

        orders: List[PendingOrder] = []
        cash_available = cash

        for ts_code, pos in current_positions.items():
            if self._check_sell(pos, top_ts_codes, sell_rank_ts_codes, score_map, close_prices):
                sell_price = close_prices.get(ts_code, pos.buy_price) if close_prices else pos.buy_price
                orders.append(PendingOrder(
                    ts_code=pos.ts_code,
                    stock_name=pos.stock_name,
                    order_price=sell_price,
                    order_shares=-pos.shares,
                    score=pos.entry_score,
                    up_prob_3d=pos.entry_3d_prob,
                    up_prob_5d=pos.entry_5d_prob,
                    trade_date=trade_date,
                    settle_date=self._next_trade_date(trade_date),
                ))

        held_ts_codes = set(current_positions.keys())

        total_value = cash
        if close_prices:
            for ts_code, pos in current_positions.items():
                price = close_prices.get(ts_code, 0)
                if price > 0:
                    total_value += pos.shares * price
        max_allowed_per_stock = total_value * self.max_position_pct

        sell_ts_codes = {order.ts_code for order in orders}
        for stock in top_stocks:
            if stock.ts_code in sell_ts_codes:
                continue
            if stock.ts_code in held_ts_codes:
                if not close_prices:
                    continue
                pos = current_positions[stock.ts_code]
                current_price = close_prices.get(stock.ts_code, 0)
                if current_price <= 0:
                    continue
                pos_value = pos.shares * current_price
                remaining_capacity = max_allowed_per_stock - pos_value
                if remaining_capacity <= self.min_order_value:
                    continue
                buy_order = self._allocate_buy(cash_available, stock, trade_date, remaining_capacity)
            else:
                buy_order = self._allocate_buy(cash_available, stock, trade_date)
            if buy_order is not None:
                cash_available -= buy_order.order_price * buy_order.order_shares
                cash_available -= max(
                    buy_order.order_price * buy_order.order_shares * self.account_config.buy_fee_rate,
                    self.account_config.min_fee,
                )
                orders.append(buy_order)

        return orders

    def _check_sell(
        self,
        position: PositionEmbed,
        top_ts_codes: set,
        sell_rank_ts_codes: set,
        score_map: Dict[str, float],
        close_prices: Optional[Dict[str, float]] = None,
    ) -> bool:
        """Check whether a position should be sold."""
        current_score = score_map.get(position.ts_code, 0.0)
        
        if current_score < self.sell_threshold:
            return True
        
        if position.hold_days >= self.max_hold_days:
            return True
        
        if close_prices and position.ts_code in close_prices:
            current_price = close_prices[position.ts_code]
            if current_price < position.buy_price * (1 + self.stop_loss_pct):
                return True
        
        if position.ts_code not in sell_rank_ts_codes:
            if current_score < self.hold_score_threshold:
                return True
        
        return False

    def _allocate_buy(
        self,
        cash: float,
        scored_stock: ScoredStock,
        trade_date: str,
        max_cost_override: Optional[float] = None,
    ) -> Optional[PendingOrder]:
        """Allocate cash to buy a stock."""
        max_cost = max_cost_override if max_cost_override is not None else cash * self.max_position_pct
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
        fee = self.calc_buy_fee(total_cost, fee_rate, self.account_config.min_fee)
        if total_cost + fee > cash:
            shares = int((cash - self.account_config.min_fee) / price / 100) * 100
            if shares < 100:
                return None
            total_cost = shares * price
            fee = self.calc_buy_fee(total_cost, fee_rate, self.account_config.min_fee)
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
