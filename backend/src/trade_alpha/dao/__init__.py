"""DAO module with Beanie Document models."""

from trade_alpha.dao.mongodb import init_db, get_db, close_db
from trade_alpha.dao.portfolio import AccountConfig
from trade_alpha.dao.strategy import StrategyConfig
from trade_alpha.dao.model_config import ModelConfig
from trade_alpha.dao.training import TrainingResult
from trade_alpha.dao.backtest import BacktestResult
from trade_alpha.dao.backtest_trade import BacktestTrade
from trade_alpha.dao.backtest_portfolio_daily import BacktestPortfolioDaily
from trade_alpha.dao.prediction import PredictionResult
from trade_alpha.dao.signal import SignalResult
from trade_alpha.dao.stock_daily import StockDaily
from trade_alpha.dao.stock_list import StockList

__all__ = [
    "init_db",
    "get_db",
    "close_db",
    "AccountConfig",
    "StrategyConfig",
    "ModelConfig",
    "TrainingResult",
    "BacktestResult",
    "BacktestTrade",
    "BacktestPortfolioDaily",
    "PredictionResult",
    "SignalResult",
    "StockDaily",
    "StockList",
]
