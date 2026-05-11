"""Backtest module."""

from trade_alpha.dao import BacktestResult, BacktestTrade
from trade_alpha.backtest.engine import BacktestEngine, BacktestResult as EngineBacktestResult
from trade_alpha.backtest.service import (
    run_backtest,
    get_backtest_by_id,
    list_backtests,
    delete_backtest,
)

__all__ = [
    "BacktestResult",
    "BacktestTrade",
    "BacktestEngine",
    "EngineBacktestResult",
    "run_backtest",
    "get_backtest_by_id",
    "list_backtests",
    "delete_backtest",
]
