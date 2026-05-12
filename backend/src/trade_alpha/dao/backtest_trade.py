"""BacktestTrade Document model."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document, PydanticObjectId


class BacktestTrade(Document):
    """Backtest trade document for MongoDB."""
    
    backtest_id: PydanticObjectId
    account_config_id: Optional[PydanticObjectId] = None
    strategy_id: Optional[PydanticObjectId] = None
    training_id: Optional[PydanticObjectId] = None
    ts_code: str
    trade_date: str
    action: str
    price: float
    shares: int
    fee: float
    cash_after: float
    position_after: int
    
    class Settings:
        name = "backtest_trades"
        indexes = [
            "backtest_id",
            "ts_code",
            "trade_date",
        ]
