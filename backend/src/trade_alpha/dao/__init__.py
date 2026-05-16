"""DAO module with Beanie Document models."""

from trade_alpha.dao.mongodb import init_db, get_db, close_db
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.strategy import StrategyConfig
from trade_alpha.dao.model_config import ModelConfig
from trade_alpha.dao.training import TrainingResult
from trade_alpha.dao.execution import ExecutionResult
from trade_alpha.dao.execution_trade import ExecutionTrade
from trade_alpha.dao.execution_daily_snapshot import ExecutionDailySnapshot
from trade_alpha.dao.prediction import PredictionResult
from trade_alpha.dao.signal import SignalResult
from trade_alpha.dao.stock_daily import StockDaily
from trade_alpha.dao.stock_list import StockList
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.dao.order_suggestion import OrderSuggestion
from trade_alpha.dao.task import Task, TaskStatus, TaskType

__all__ = [
    "OrderSuggestion",
    "Task",
    "TaskStatus",
    "TaskType",
    "init_db",
    "get_db",
    "close_db",
    "AccountConfig",
    "StrategyConfig",
    "ModelConfig",
    "TrainingResult",
    "ExecutionResult",
    "ExecutionTrade",
    "ExecutionDailySnapshot",
    "PredictionResult",
    "SignalResult",
    "StockDaily",
    "StockList",
    "PositionEmbed",
]
