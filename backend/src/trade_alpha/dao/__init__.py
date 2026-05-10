"""DAO module with Beanie Document models."""

from trade_alpha.dao.mongodb import init_db, get_db, close_db
from trade_alpha.dao.portfolio import Portfolio
from trade_alpha.dao.strategy import Strategy
from trade_alpha.dao.model_config import ModelConfig
from trade_alpha.dao.training import Training
from trade_alpha.dao.backtest import Backtest
from trade_alpha.dao.backtest_trade import BacktestTrade
from trade_alpha.dao.prediction import Prediction
from trade_alpha.dao.signal import Signal
from trade_alpha.dao.stock_daily import StockDaily
from trade_alpha.dao.stock_list import StockList

__all__ = [
    "init_db",
    "get_db",
    "close_db",
    "Portfolio",
    "Strategy",
    "ModelConfig",
    "Training",
    "Backtest",
    "BacktestTrade",
    "Prediction",
    "Signal",
    "StockDaily",
    "StockList",
]
