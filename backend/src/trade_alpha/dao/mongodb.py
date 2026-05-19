"""MongoDB initialization module."""

from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie, PydanticObjectId
from trade_alpha.config import load_config
from trade_alpha.logging import get_logger

logger = get_logger("dao")

_db_client: Optional[AsyncIOMotorClient] = None


async def init_db():
    """Initialize Beanie ODM."""
    global _db_client

    config = load_config()
    _db_client = AsyncIOMotorClient(config.mongodb_uri)
    database = _db_client[config.mongodb_db]

    from trade_alpha.dao.account_config import AccountConfig
    from trade_alpha.dao.strategy_config import StrategyConfig
    from trade_alpha.dao.model_config import ModelConfig
    from trade_alpha.dao.training import TrainingResult
    from trade_alpha.dao.execution import ExecutionResult
    from trade_alpha.dao.execution_trade import ExecutionTrade
    from trade_alpha.dao.execution_daily_snapshot import ExecutionDailySnapshot
    from trade_alpha.dao.prediction import PredictionResult
    from trade_alpha.dao.signal import SignalResult
    from trade_alpha.dao.stock_daily import StockDaily
    from trade_alpha.dao.stock_list import StockList
    from trade_alpha.dao.order_suggestion import OrderSuggestion
    from trade_alpha.dao.task import Task
    from trade_alpha.dao.data_analysis_result import DataAnalysisResult

    await init_beanie(
        database=database,
        document_models=[
            AccountConfig,
            StrategyConfig,
            ModelConfig,
            TrainingResult,
            ExecutionResult,
            ExecutionTrade,
            ExecutionDailySnapshot,
            PredictionResult,
            SignalResult,
            StockDaily,
            StockList,
            OrderSuggestion,
            Task,
            DataAnalysisResult,
        ]
    )
    logger.info("init_db", f"Beanie initialized for {config.mongodb_db}")


def get_db() -> Optional[AsyncIOMotorClient]:
    """Get database client."""
    return _db_client


async def get_database():
    """Get database instance for raw operations."""
    if _db_client is None:
        return None
    config = load_config()
    return _db_client[config.mongodb_db]


async def close_db():
    """Close database connection."""
    global _db_client
    if _db_client:
        _db_client.close()
        _db_client = None
        logger.info("close_db", "Database connection closed")
