"""Position manager for backtest execution pipeline."""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
from beanie import PydanticObjectId
import numpy as np
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.dao.execution_trade import ExecutionTrade
from trade_alpha.dao.execution_portfolio_daily import ExecutionPortfolioDaily
from trade_alpha.dao.order_suggestion import OrderSuggestion
from trade_alpha.execution.schemas import ScoredStock, PendingOrder
from trade_alpha.logging import get_logger

logger = get_logger("execution.position_manager")

RISK_FREE_RATE = 0.03
TRADING_DAYS = 252


class PositionManager:
    """Position management: ranking, selling, buying, settlement, and snapshots."""

    def __init__(
        self,
        account_config: AccountConfig,
        max_positions: int = 10,
        max_position_pct: float = 0.3,
        min_order_value: float = 5000,
        stop_loss_pct: float = -0.1,
        max_hold_days: int = 20,
    ):
        self.account_config = account_config
        self.max_positions = max_positions
        self.max_position_pct = max_position_pct
        self.min_order_value = min_order_value
        self.stop_loss_pct = stop_loss_pct
        self.max_hold_days = max_hold_days

    async def make_decisions(
        self,
        scored_stocks: List[ScoredStock],
        current_positions: Dict[str, PositionEmbed],
        cash: float,
        trade_date: str,
        close_prices: Optional[Dict[str, float]] = None,
    ) -> List[PendingOrder]:
        """Unified ranking and position adjustment.

        Sort all scored stocks by score descending, sell positions that fall
        out of the top N or meet exit conditions, then buy top-ranked stocks
        that are not yet held.

        Args:
            scored_stocks: Ranked stocks with prediction scores.
            current_positions: Currently held positions dict (ts_code -> PositionEmbed).
            cash: Current cash balance.
            trade_date: Current trading date.
            close_prices: Optional mapping of ts_code -> close price for accurate
                          sell proceeds estimation. Falls back to buy_price if not provided.

        Returns:
            List of PendingOrder (positive shares = buy, negative shares = sell).
        """
        sorted_stocks = sorted(scored_stocks, key=lambda s: s.score, reverse=True)
        top_stocks = sorted_stocks[:self.max_positions]
        top_ts_codes = {s.ts_code for s in top_stocks}

        orders: List[PendingOrder] = []
        cash_available = cash

        for ts_code, pos in current_positions.items():
            if self._check_sell(pos, top_ts_codes, close_prices=close_prices):
                sell_price = close_prices.get(ts_code, pos.buy_price) if close_prices else pos.buy_price
                sell_value = sell_price * pos.shares
                sell_fee = max(sell_value * self.account_config.sell_fee_rate, self.account_config.min_fee)
                stamp_tax = sell_value * self.account_config.stamp_tax_rate
                cash_available += sell_value - sell_fee - stamp_tax
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
        for stock in top_stocks:
            if stock.ts_code in held_ts_codes:
                continue
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
        close_prices: Optional[Dict[str, float]] = None,
    ) -> bool:
        """Check whether a position should be sold.

        Sell conditions (any one triggers a sell):
        1. Stock is not in the top N ranking
        2. Hold days exceed max_hold_days
        3. Current price drops below stop_loss_pct from buy price (if close_prices provided)
        """
        if position.ts_code not in top_ts_codes:
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
        """Allocate cash to buy a stock.

        Returns a PendingOrder if the cash is sufficient, otherwise None.
        Shares are rounded down to the nearest round lot (100 for A-shares).
        """
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

    async def settle_orders(
        self,
        orders: List[PendingOrder],
        date: str,
        close_prices: Dict[str, float],
        backtest_id: PydanticObjectId = None,
    ) -> Tuple[List[ExecutionTrade], float]:
        """Settle pending orders using actual close prices.

        Args:
            orders: Pending orders to settle.
            date: Settlement date.
            close_prices: Mapping of ts_code -> close price.
            backtest_id: ID of the backtest execution.

        Returns:
            Tuple of (list of ExecutionTrade records, net cash change).
        """
        trades: List[ExecutionTrade] = []
        net_cash_change = 0.0

        for order in orders:
            price = close_prices.get(order.ts_code, order.order_price)
            shares = abs(order.order_shares)
            action = "buy" if order.order_shares > 0 else "sell"

            if action == "buy":
                fee = max(price * shares * self.account_config.buy_fee_rate, self.account_config.min_fee)
                cash_after = -price * shares - fee
            else:
                fee = max(price * shares * self.account_config.sell_fee_rate, self.account_config.min_fee)
                stamp_tax = price * shares * self.account_config.stamp_tax_rate
                cash_after = price * shares - fee - stamp_tax

            net_cash_change += cash_after
            trades.append(ExecutionTrade(
                backtest_id=backtest_id,
                ts_code=order.ts_code,
                trade_date=date,
                action=action,
                price=price,
                shares=shares if action == "buy" else -shares,
                fee=fee,
                cash_after=cash_after,
                reason=f"rank_{'buy' if action == 'buy' else 'sell'}",
                entry_score=order.score,
                up_prob_3d=order.up_prob_3d,
                up_prob_5d=order.up_prob_5d,
            ))

        return trades, net_cash_change

    async def daily_snapshot(
        self,
        backtest_id: PydanticObjectId,
        date: str,
        cash: float,
        positions: Dict[str, PositionEmbed],
        close_prices: Dict[str, float],
        prev_total_value: Optional[float] = None,
    ) -> ExecutionPortfolioDaily:
        """Create and save daily portfolio snapshot.

        Args:
            backtest_id: ID of the backtest execution.
            date: Snapshot date.
            cash: Current cash balance.
            positions: Current positions dict.
            close_prices: Mapping of ts_code -> close price for valuation.
            prev_total_value: Previous day total value for day_return calculation.

        Returns:
            The saved ExecutionPortfolioDaily document.
        """
        pos_list: List[PositionEmbed] = []
        total_market_value = 0.0

        for ts_code, pos in positions.items():
            price = close_prices.get(ts_code, pos.buy_price)
            market_value = price * pos.shares
            total_market_value += market_value

            updated_pos = PositionEmbed(
                ts_code=pos.ts_code,
                stock_name=pos.stock_name,
                buy_date=pos.buy_date,
                buy_price=pos.buy_price,
                shares=pos.shares,
                fee=pos.fee,
                entry_score=pos.entry_score,
                entry_3d_prob=pos.entry_3d_prob,
                entry_5d_prob=pos.entry_5d_prob,
                hold_days=pos.hold_days + 1,
            )
            pos_list.append(updated_pos)

        total_value = cash + total_market_value
        day_return = 0.0
        if prev_total_value is not None and prev_total_value > 0:
            day_return = (total_value - prev_total_value) / prev_total_value

        snapshot = ExecutionPortfolioDaily(
            backtest_id=backtest_id,
            date=date,
            cash=cash,
            positions=pos_list,
            total_market_value=total_market_value,
            total_value=total_value,
            day_return=day_return,
        )
        await snapshot.insert()
        return snapshot

    @staticmethod
    def _next_trade_date(date_str: str) -> str:
        """Return the next trading date skipping weekends."""
        from datetime import datetime, timedelta
        dt = datetime.strptime(date_str, "%Y%m%d")
        dt += timedelta(days=1)
        while dt.weekday() >= 5:
            dt += timedelta(days=1)
        return dt.strftime("%Y%m%d")

    @staticmethod
    def calculate_metrics(daily_returns: List[float]) -> Dict[str, float]:
        """Calculate Sharpe ratio, volatility from daily returns.

        Args:
            daily_returns: List of daily return values (e.g., [0.01, -0.02, 0.03])

        Returns:
            Dict with sharpe_ratio and volatility
        """
        if not daily_returns:
            return {"sharpe_ratio": 0.0, "volatility": 0.0}

        returns = np.array(daily_returns)
        mean_return = np.mean(returns)
        std_return = np.std(returns)

        daily_rf = RISK_FREE_RATE / TRADING_DAYS
        sharpe_ratio = (mean_return - daily_rf) / std_return if std_return > 0 else 0.0
        volatility = std_return * np.sqrt(TRADING_DAYS)

        return {
            "sharpe_ratio": float(sharpe_ratio),
            "volatility": float(volatility),
        }

    @staticmethod
    def calculate_max_drawdown(values: List[float]) -> float:
        """Calculate maximum drawdown from portfolio values.

        Args:
            values: List of portfolio values over time

        Returns:
            Maximum drawdown as a positive percentage (e.g., 0.05 for 5%)
        """
        if not values or len(values) < 2:
            return 0.0

        values_arr = np.array(values)
        peak = values_arr[0]
        max_dd = 0.0

        for value in values_arr:
            if value > peak:
                peak = value
            dd = (peak - value) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

        return float(max_dd)

    @staticmethod
    def calculate_baseline_metrics(
        start_price: float,
        end_price: float,
        daily_prices: List[float],
    ) -> Dict[str, float]:
        """Calculate baseline metrics for buy-and-hold strategy.

        Args:
            start_price: Buy price on first day
            end_price: Sell price on last day
            daily_prices: List of daily close prices

        Returns:
            Dict with baseline_return and baseline_max_drawdown
        """
        if not daily_prices or start_price <= 0:
            return {"baseline_return": 0.0, "baseline_max_drawdown": 0.0}

        baseline_return = (end_price - start_price) / start_price

        values = [price / daily_prices[0] * start_price for price in daily_prices]
        baseline_max_drawdown = PositionManager.calculate_max_drawdown(values)

        return {
            "baseline_return": float(baseline_return),
            "baseline_max_drawdown": float(baseline_max_drawdown),
        }

    async def calculate_trade_metrics(
        self,
        trades: List[ExecutionTrade],
        daily_snapshots: List[ExecutionPortfolioDaily],
    ) -> Dict[str, float]:
        """Calculate trading metrics including avg_hold_days.

        Args:
            trades: List of execution trades
            daily_snapshots: List of daily portfolio snapshots

        Returns:
            Dict with avg_hold_days
        """
        if not trades:
            return {"avg_hold_days": 0.0}

        buy_trades = [t for t in trades if t.action == "buy"]
        if not buy_trades:
            return {"avg_hold_days": 0.0}

        hold_days_list = []
        for buy_trade in buy_trades:
            sell_trade = next(
                (t for t in trades if t.action == "sell" and t.ts_code == buy_trade.ts_code and t.trade_date > buy_trade.trade_date),
                None
            )
            if sell_trade:
                from datetime import datetime
                buy_dt = datetime.strptime(buy_trade.trade_date, "%Y%m%d")
                sell_dt = datetime.strptime(sell_trade.trade_date, "%Y%m%d")
                hold_days = (sell_dt - buy_dt).days
                hold_days_list.append(hold_days)

        avg_hold_days = float(np.mean(hold_days_list)) if hold_days_list else 0.0

        return {
            "avg_hold_days": avg_hold_days,
        }
