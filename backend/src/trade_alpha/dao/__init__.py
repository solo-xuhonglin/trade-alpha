"""DAO module."""

from trade_alpha.dao.mongodb import MongoDB
from trade_alpha.dao.stock_daily_dao import StockDailyDAO
from trade_alpha.dao.stock_list_dao import StockListDAO
from trade_alpha.dao.portfolio_dao import PortfolioDAO
from trade_alpha.dao.strategy_dao import StrategyDAO
from trade_alpha.dao.model_config_dao import ModelConfigDAO
from trade_alpha.dao.training_dao import TrainingDAO
from trade_alpha.dao.backtest_dao import BacktestDAO
from trade_alpha.dao.backtest_trade_dao import BacktestTradeDAO
from trade_alpha.dao.prediction_dao import PredictionDAO
from trade_alpha.dao.signal_dao import SignalDAO

__all__ = [
    "MongoDB",
    "StockDailyDAO",
    "StockListDAO",
    "PortfolioDAO",
    "StrategyDAO",
    "ModelConfigDAO",
    "TrainingDAO",
    "BacktestDAO",
    "BacktestTradeDAO",
    "PredictionDAO",
    "SignalDAO",
]
