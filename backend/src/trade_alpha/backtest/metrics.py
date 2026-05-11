"""Metrics calculation module."""

from dataclasses import dataclass
from typing import List, Tuple
from trade_alpha.account import TradeRecord


@dataclass
class Metrics:
    """Backtest metrics container."""
    total_return: float = 0.0
    annual_return: float = 0.0
    benchmark_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    avg_holding_days: float = 0.0
    total_fees: float = 0.0


def calculate_metrics(
    trades: List[TradeRecord],
    daily_values: List[Tuple[str, float]],
    initial_capital: float,
    benchmark_return: float,
) -> Metrics:
    """Calculate backtest metrics."""
    if not daily_values:
        return Metrics(benchmark_return=benchmark_return)

    dates = [v[0] for v in daily_values]
    values = [v[1] for v in daily_values]

    total_return = (values[-1] - initial_capital) / initial_capital if initial_capital > 0 else 0.0

    days = (len(dates) - 1)
    annual_return = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0.0

    max_drawdown = calculate_max_drawdown(values)

    returns = [(values[i] - values[i-1]) / values[i-1] for i in range(1, len(values))]
    sharpe_ratio = calculate_sharpe_ratio(returns)

    win_rate, profit_factor, avg_holding_days = calculate_trade_metrics(trades, dates)

    total_fees = sum(t.fee for t in trades)

    return Metrics(
        total_return=total_return,
        annual_return=annual_return,
        benchmark_return=benchmark_return,
        max_drawdown=max_drawdown,
        sharpe_ratio=sharpe_ratio,
        win_rate=win_rate,
        profit_factor=profit_factor,
        total_trades=len(trades),
        avg_holding_days=avg_holding_days,
        total_fees=total_fees,
    )


def calculate_max_drawdown(values: List[float]) -> float:
    """Calculate maximum drawdown."""
    if not values:
        return 0.0

    max_so_far = values[0]
    max_drawdown = 0.0

    for value in values[1:]:
        max_so_far = max(max_so_far, value)
        drawdown = (max_so_far - value) / max_so_far if max_so_far > 0 else 0.0
        max_drawdown = max(max_drawdown, drawdown)

    return max_drawdown


def calculate_sharpe_ratio(returns: List[float]) -> float:
    """Calculate Sharpe ratio (assuming 0 risk-free rate)."""
    if not returns:
        return 0.0

    import numpy as np
    mean_return = np.mean(returns)
    std_return = np.std(returns)

    if std_return == 0:
        return 0.0

    return mean_return / std_return * np.sqrt(252)


def calculate_trade_metrics(trades: List[TradeRecord], dates: List[str]) -> Tuple[float, float, float]:
    """Calculate trade-related metrics."""
    if not trades:
        return 0.0, 0.0, 0.0

    buy_trades = [t for t in trades if t.action == "buy"]
    sell_trades = [t for t in trades if t.action == "sell"]

    winning_trades = 0
    total_profit = 0.0
    total_loss = 0.0
    holding_days = 0.0

    for i, buy in enumerate(buy_trades):
        if i < len(sell_trades):
            sell = sell_trades[i]
            profit = (sell.price - buy.price) * buy.shares - buy.fee - sell.fee
            if profit > 0:
                winning_trades += 1
                total_profit += profit
            else:
                total_loss += abs(profit)

    win_rate = winning_trades / len(buy_trades) if buy_trades else 0.0
    profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')

    return win_rate, profit_factor, holding_days / len(buy_trades) if buy_trades else 0.0
