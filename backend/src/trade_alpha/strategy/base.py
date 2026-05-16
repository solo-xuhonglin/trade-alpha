from datetime import datetime
from typing import Dict, List, Optional, Tuple
from beanie import PydanticObjectId
import numpy as np
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.dao.execution_trade import ExecutionTrade
from trade_alpha.dao.execution_daily_snapshot import ExecutionDailySnapshot
from trade_alpha.schemas import ScoredStock, PendingOrder
from trade_alpha.logging import get_logger

logger = get_logger("strategy.base")

RISK_FREE_RATE = 0.03
TRADING_DAYS = 252


class PositionManager:
    """Position manager base class with common functionality."""

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
        """Make buy/sell decisions (to be implemented by subclasses)."""
        raise NotImplementedError("Subclasses must implement make_decisions")

    async def settle_orders(
        self,
        orders: List[PendingOrder],
        date: str,
        close_prices: Dict[str, float],
        backtest_id: PydanticObjectId = None,
    ) -> Tuple[List[ExecutionTrade], float]:
        """Settle pending orders using actual close prices."""
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
        predictions: Optional[Dict[str, Dict]] = None,
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
                hold_days=pos.hold_days + 1,
            )
            pos_list.append(updated_pos)

        total_value = cash + total_market_value
        day_return = 0.0
        if prev_total_value is not None and prev_total_value > 0:
            day_return = (total_value - prev_total_value) / prev_total_value

        def _convert_to_native(obj):
            """Convert numpy types to Python native types."""
            import numpy as np
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, (np.integer, np.floating)):
                return obj.item()
            if isinstance(obj, dict):
                return {k: _convert_to_native(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_convert_to_native(item) for item in obj]
            return obj

        snapshot = ExecutionDailySnapshot(
            backtest_id=backtest_id,
            date=date,
            cash=cash,
            positions=pos_list,
            total_market_value=total_market_value,
            total_value=total_value,
            day_return=day_return,
            predictions=_convert_to_native(predictions) if predictions else {},
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
        """Calculate Sharpe ratio, volatility from daily returns."""
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
