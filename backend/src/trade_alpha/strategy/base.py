from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from beanie import PydanticObjectId
import numpy as np
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.dao.execution_trade import ExecutionTrade
from trade_alpha.dao.execution_daily_snapshot import ExecutionDailySnapshot
from trade_alpha.schemas import ScoredStock, PendingOrder, MarketDataEmbed
from trade_alpha.logging import get_logger
from trade_alpha.execution.context import PipelineContext

logger = get_logger("strategy.base")

RISK_FREE_RATE = 0.03
TRADING_DAYS = 252


class BaseStrategy:
    """Base strategy class with common functionality."""

    def __init__(
        self,
        max_positions: int = 10,
        max_position_pct: float = 0.3,
        min_order_value: float = 5000,
        stop_loss_pct: float = -0.1,
        max_hold_days: int = 20,
        buy_threshold: float = 0.1,
        sell_threshold: float = -0.1,
        min_hold_days: int = 3,
    ):
        self.max_positions = max_positions
        self.max_position_pct = max_position_pct
        self.min_order_value = min_order_value
        self.stop_loss_pct = stop_loss_pct
        self.max_hold_days = max_hold_days
        self.min_hold_days = min_hold_days
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    async def make_orders(
        self,
        scored_stocks: List[ScoredStock],
        trade_date: str,
        ctx: PipelineContext,
        close_prices: Optional[Dict[str, float]] = None,
        market_data: Optional[MarketDataEmbed] = None,
        suggestion_mode: bool = False,
        atr_values: Optional[Dict[str, float]] = None,
    ) -> List[PendingOrder]:
        """Make buy/sell decisions (to be implemented by subclasses)."""
        raise NotImplementedError("Subclasses must implement make_orders")

    @staticmethod
    def calc_buy_fee(cost: float, fee_rate: float, min_fee: float) -> float:
        """Calculate buy fee as cost * fee_rate, floored by min_fee."""
        return max(cost * fee_rate, min_fee)

    @staticmethod
    def match_order(order: PendingOrder, open_px: float, high_px: float, low_px: float) -> Optional[float]:
        """Match a pending order against next day's OHLC. Returns matched price or None."""
        if order.order_shares > 0:  # Buy - 限价买入，价格需不高于 order_price
            if order.order_price >= open_px:
                return open_px
            if low_px <= order.order_price:
                return order.order_price
            return None
        else:  # Sell - 限价卖出，价格需不低于 order_price
            if order.order_price <= open_px:
                return open_px
            if high_px >= order.order_price:
                return order.order_price
            return None

    async def settle_orders(
        self,
        orders: List[PendingOrder],
        date: str,
        open_prices: Dict[str, float],
        high_prices: Dict[str, float],
        low_prices: Dict[str, float],
        backtest_id: Optional[PydanticObjectId] = None,
        cash: Optional[float] = None,
        buy_fee_rate: float = 0,
        sell_fee_rate: float = 0,
        stamp_tax_rate: float = 0,
        min_fee: float = 0,
    ) -> Tuple[List[ExecutionTrade], List[PendingOrder], float]:
        """Settle pending orders using T+1 OHLC matching.

        Fee rates are passed explicitly by the caller (pipeline) rather than
        stored on the strategy, keeping fee configuration out of strategy layer.

        Processes sell orders first to increase available cash, then processes buy
        orders with a cash sufficiency check to prevent negative cash balance.
        """
        filled_trades: List[ExecutionTrade] = []
        unfilled_orders: List[PendingOrder] = []
        net_cash_change = 0.0

        sell_orders = [o for o in orders if o.order_shares < 0]
        buy_orders = [o for o in orders if o.order_shares > 0]

        for order in sell_orders + buy_orders:
            open_px = open_prices.get(order.ts_code)
            high_px = high_prices.get(order.ts_code)
            low_px = low_prices.get(order.ts_code)
            if open_px is None or high_px is None or low_px is None:
                unfilled_orders.append(order)
                continue

            matched_price = self.match_order(order, open_px, high_px, low_px)
            if matched_price is None:
                unfilled_orders.append(order)
                continue

            shares = abs(order.order_shares)
            action = "buy" if order.order_shares > 0 else "sell"

            if action == "buy":
                fee = self.calc_buy_fee(matched_price * shares, buy_fee_rate, min_fee)
                cost = matched_price * shares + fee
                if cash is not None and cash + net_cash_change < cost:
                    unfilled_orders.append(order)
                    continue
                cash_after = -cost
            else:
                fee = max(matched_price * shares * sell_fee_rate, min_fee)
                stamp_tax = matched_price * shares * stamp_tax_rate
                cash_after = matched_price * shares - fee - stamp_tax

            net_cash_change += cash_after
            filled_trades.append(ExecutionTrade(
                backtest_id=backtest_id,
                ts_code=order.ts_code,
                trade_date=date,
                action=action,
                filled_price=matched_price,
                order_price=order.order_price,
                shares=shares if action == "buy" else -shares,
                fee=fee,
                cash_after=cash_after,
                status="filled",
                reason=order.reason or f"rank_{action}",
                entry_score=order.entry_score,
                up_prob_3d=order.up_prob_3d,
                up_prob_5d=order.up_prob_5d,
                up_prob_10d=order.up_prob_10d,
                up_prob_20d=order.up_prob_20d,
                candidate_group=order.candidate_group,
            ))

        return filled_trades, unfilled_orders, net_cash_change

    async def daily_snapshot(
        self,
        backtest_id: PydanticObjectId,
        date: str,
        cash: float,
        positions: Dict[str, PositionEmbed],
        close_prices: Dict[str, float],
        prev_total_value: Optional[float] = None,
        predictions: Optional[Dict[str, ScoredStock]] = None,
        baseline_value: Optional[float] = None,
    ) -> ExecutionDailySnapshot:
        """Create and save daily portfolio snapshot."""
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
                entry_10d_prob=pos.entry_10d_prob,
                entry_20d_prob=pos.entry_20d_prob,
                hold_days=pos.hold_days,
                atr_at_entry=pos.atr_at_entry,
            )
            pos_list.append(updated_pos)

        total_value = cash + total_market_value
        day_return = 0.0
        if prev_total_value is not None and prev_total_value > 0:
            day_return = (total_value - prev_total_value) / prev_total_value

        snapshot = ExecutionDailySnapshot(
            backtest_id=backtest_id,
            date=date,
            cash=cash,
            positions=pos_list,
            total_market_value=total_market_value,
            total_value=total_value,
            day_return=day_return,
            predictions=predictions or {},
            baseline_value=baseline_value or 0.0,
        )
        await snapshot.insert()
        return snapshot

    @staticmethod
    def _next_trade_date(date_str: str) -> str:
        """Return the next trading date skipping weekends."""
        from datetime import timedelta
        dt = datetime.strptime(date_str, "%Y%m%d")
        dt += timedelta(days=1)
        while dt.weekday() >= 5:
            dt += timedelta(days=1)
        return dt.strftime("%Y%m%d")

    @staticmethod
    def calculate_metrics(daily_returns: List[float]) -> Dict[str, float]:
        """Calculate Sharpe ratio, volatility, annual return from daily returns."""
        if not daily_returns:
            return {"sharpe_ratio": 0.0, "volatility": 0.0, "annual_return": 0.0}

        returns = np.array(daily_returns)
        mean_return = np.mean(returns)
        std_return = np.std(returns)

        daily_rf = RISK_FREE_RATE / TRADING_DAYS
        sharpe_ratio = (mean_return - daily_rf) / std_return * np.sqrt(TRADING_DAYS) if std_return > 0 else 0.0
        volatility = std_return * np.sqrt(TRADING_DAYS)

        cumulative_return = float(np.prod(1 + returns) - 1)
        n_days = len(returns)
        total_return_factor = max(1 + cumulative_return, 0)
        annual_return = total_return_factor ** (TRADING_DAYS / n_days) - 1 if n_days > 0 else 0.0

        return {
            "sharpe_ratio": float(sharpe_ratio),
            "volatility": float(volatility),
            "annual_return": float(annual_return),
        }

    @staticmethod
    def calculate_max_drawdown(values: List[float]) -> float:
        """Calculate maximum drawdown from portfolio values."""
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
        """Calculate baseline metrics for buy-and-hold strategy."""
        if not daily_prices or start_price <= 0:
            return {"baseline_return": 0.0, "baseline_max_drawdown": 0.0,
                    "baseline_annual_return": 0.0, "baseline_volatility": 0.0,
                    "baseline_sharpe_ratio": 0.0}

        baseline_return = (end_price - start_price) / start_price

        values = [price / daily_prices[0] * start_price for price in daily_prices]
        baseline_max_drawdown = BaseStrategy.calculate_max_drawdown(values)

        baseline_daily_returns = [
            (daily_prices[i] - daily_prices[i-1]) / daily_prices[i-1]
            for i in range(1, len(daily_prices))
        ]
        returns = np.array(baseline_daily_returns) if baseline_daily_returns else np.array([0.0])
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        daily_rf = RISK_FREE_RATE / TRADING_DAYS
        baseline_sharpe_ratio = (mean_return - daily_rf) / std_return * np.sqrt(TRADING_DAYS) if std_return > 0 else 0.0
        baseline_volatility = std_return * np.sqrt(TRADING_DAYS)

        n_days = len(daily_prices)
        baseline_annual_return = (1 + baseline_return) ** (TRADING_DAYS / n_days) - 1 if n_days > 0 else 0.0

        return {
            "baseline_return": float(baseline_return),
            "baseline_max_drawdown": float(baseline_max_drawdown),
            "baseline_annual_return": float(baseline_annual_return),
            "baseline_volatility": float(baseline_volatility),
            "baseline_sharpe_ratio": float(baseline_sharpe_ratio),
        }

    async def calculate_trade_metrics(
        self,
        trades: List[ExecutionTrade],
        daily_snapshots: List[ExecutionDailySnapshot],
    ) -> Dict[str, float]:
        """Calculate trading metrics including avg_hold_days."""
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
                buy_dt = datetime.strptime(buy_trade.trade_date, "%Y%m%d")
                sell_dt = datetime.strptime(sell_trade.trade_date, "%Y%m%d")
                hold_days = (sell_dt - buy_dt).days
                hold_days_list.append(hold_days)

        avg_hold_days = float(np.mean(hold_days_list)) if hold_days_list else 0.0

        return {
            "avg_hold_days": avg_hold_days,
        }
