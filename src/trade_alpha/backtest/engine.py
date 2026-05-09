"""Backtest engine module."""

from dataclasses import dataclass
from typing import List, Dict
from unittest.mock import MagicMock
from trade_alpha.portfolio import Portfolio, Trade


@dataclass
class BacktestResult:
    """Backtest result container."""
    backtest_id: str = ""
    portfolio_id: str = ""
    ts_code: str = ""
    start_date: str = ""
    end_date: str = ""
    strategy: str = ""
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


class BacktestEngine:
    """Backtest engine for running trading strategies on historical data."""

    def __init__(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
        strategy,
        portfolio: Portfolio,
    ):
        self.ts_code = ts_code
        self.start_date = start_date
        self.end_date = end_date
        self.strategy = strategy
        self.portfolio = portfolio
        self.daily_values = []

    def _calculate_max_shares(self, price: float) -> int:
        """Calculate maximum shares that can be bought with current cash."""
        cash = self.portfolio.cash
        shares = int(cash / price)
        while shares > 0:
            fee = self.portfolio._calculate_buy_fee(price, shares)
            if shares * price + fee <= cash:
                break
            shares -= 1
        return shares

    def run(self, records: List[Dict]) -> BacktestResult:
        """Run backtest on historical data."""
        if not records:
            return BacktestResult(
                ts_code=self.ts_code,
                start_date=self.start_date,
                end_date=self.end_date,
                initial_capital=self.portfolio.cash,
                final_value=self.portfolio.cash,
            )

        initial_capital = self.portfolio.cash
        
        for i, record in enumerate(records[:-1]):
            next_record = records[i + 1]
            
            context = MagicMock()
            context.ts_code = self.ts_code
            context.trade_date = record["trade_date"]
            context.current_price = float(record["close"])
            context.prediction = {"close": float(next_record["open"])}
            context.indicators = {}
            
            action = self.strategy.decide(context)
            
            if action == "buy" and self.portfolio.cash > 0:
                price = float(next_record["open"])
                max_shares = self._calculate_max_shares(price)
                if max_shares > 0:
                    self.portfolio.buy(next_record["trade_date"], price, max_shares)
            
            elif action == "sell" and self.portfolio.position > 0:
                price = float(next_record["open"])
                self.portfolio.sell(next_record["trade_date"], price, self.portfolio.position)

            daily_value = self.portfolio.cash + self.portfolio.position * float(record["close"])
            self.daily_values.append((record["trade_date"], daily_value))

        final_value = self.portfolio.cash + self.portfolio.position * float(records[-1]["close"])
        self.daily_values.append((records[-1]["trade_date"], final_value))
        
        total_return = (final_value - initial_capital) / initial_capital if initial_capital > 0 else 0
        
        return BacktestResult(
            ts_code=self.ts_code,
            start_date=self.start_date,
            end_date=self.end_date,
            strategy=str(self.strategy.__class__.__name__),
            initial_capital=initial_capital,
            final_value=final_value,
            total_return=total_return,
            total_trades=len(self.portfolio.trades),
            total_fees=sum(t.fee for t in self.portfolio.trades),
        )
