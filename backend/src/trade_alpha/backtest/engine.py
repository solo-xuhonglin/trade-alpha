"""Backtest engine module."""

from dataclasses import dataclass, field
from typing import List, Dict
from unittest.mock import MagicMock
from trade_alpha.account import AccountManager, TradeRecord


@dataclass
class PositionSnapshot:
    """Position snapshot for daily record."""

    ts_code: str
    shares: int


@dataclass
class DailySnapshot:
    """Daily account snapshot."""

    date: str
    cash: float
    positions: List[PositionSnapshot]
    market_value: float
    total_value: float
    position_ratio: float


@dataclass
class BacktestResult:
    """Backtest result container."""

    backtest_id: str = ""
    account_config_id: str = ""
    strategy_id: str = ""
    training_id: str = ""
    ts_code: str = ""
    start_date: str = ""
    end_date: str = ""
    initial_capital: float = 0.0
    final_value: float = 0.0
    total_return: float = 0.0
    annual_return: float = 0.0
    benchmark_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    total_fees: float = 0.0
    daily_snapshots: List[DailySnapshot] = field(default_factory=list)


class BacktestEngine:
    """Backtest engine for running trading strategies on historical data."""

    def __init__(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
        strategy,
        account_manager: AccountManager,
    ):
        self.ts_code = ts_code
        self.start_date = start_date
        self.end_date = end_date
        self.strategy = strategy
        self.account_manager = account_manager
        self.daily_values = []
        self.daily_snapshots: List[DailySnapshot] = []

    def _calculate_max_shares(self, price: float) -> int:
        """Calculate maximum shares that can be bought with current cash."""
        cash = self.account_manager.cash
        shares = int(cash / price)
        while shares > 0:
            fee = self.account_manager._calculate_buy_fee(price, shares)
            if shares * price + fee <= cash:
                break
            shares -= 1
        return shares

    def _create_daily_snapshot(self, date: str) -> DailySnapshot:
        """Create daily snapshot from current portfolio state."""
        position_value = self.account_manager.position * self._last_close
        total_value = self.account_manager.cash + position_value
        position_ratio = position_value / total_value if total_value > 0 else 0.0

        return DailySnapshot(
            date=date,
            cash=self.account_manager.cash,
            positions=[PositionSnapshot(ts_code=self.ts_code, shares=self.account_manager.position)],
            market_value=position_value,
            total_value=total_value,
            position_ratio=position_ratio,
        )

    def run(self, records: List[Dict]) -> BacktestResult:
        """Run backtest on historical data."""
        self._last_close = 0.0

        if not records:
            return BacktestResult(
                ts_code=self.ts_code,
                start_date=self.start_date,
                end_date=self.end_date,
                initial_capital=self.account_manager.cash,
                final_value=self.account_manager.cash,
            )

        initial_capital = self.account_manager.cash

        for i, record in enumerate(records[:-1]):
            next_record = records[i + 1]

            self._last_close = float(record["close"])

            self.daily_snapshots.append(self._create_daily_snapshot(record["trade_date"]))

            context = MagicMock()
            context.ts_code = self.ts_code
            context.trade_date = record["trade_date"]
            context.current_price = float(record["close"])
            context.prediction = {"close": float(next_record["open"])}
            context.indicators = {}
            context.position = self.account_manager.position

            action = self.strategy.decide(context)

            if action == "buy" and self.account_manager.cash > 0:
                price = float(next_record["open"])
                max_shares = self._calculate_max_shares(price)
                if max_shares > 0:
                    self.account_manager.buy(next_record["trade_date"], price, max_shares)

            elif action == "sell" and self.account_manager.position > 0:
                price = float(next_record["open"])
                self.account_manager.sell(next_record["trade_date"], price, self.account_manager.position)

            daily_value = self.account_manager.cash + self.account_manager.position * float(record["close"])
            self.daily_values.append((record["trade_date"], daily_value))

        self._last_close = float(records[-1]["close"])
        final_value = self.account_manager.cash + self.account_manager.position * self._last_close
        self.daily_values.append((records[-1]["trade_date"], final_value))
        self.daily_snapshots.append(self._create_daily_snapshot(records[-1]["trade_date"]))

        total_return = (final_value - initial_capital) / initial_capital if initial_capital > 0 else 0

        return BacktestResult(
            ts_code=self.ts_code,
            start_date=self.start_date,
            end_date=self.end_date,
            strategy_id=str(self.strategy.__class__.__name__),
            initial_capital=initial_capital,
            final_value=final_value,
            total_return=total_return,
            total_trades=len(self.account_manager.trades),
            total_fees=sum(t.fee for t in self.account_manager.trades),
            daily_snapshots=self.daily_snapshots,
        )
