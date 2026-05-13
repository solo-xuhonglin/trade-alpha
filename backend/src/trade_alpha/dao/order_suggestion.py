"""OrderSuggestion Document model."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document, PydanticObjectId


class OrderSuggestion(Document):
    """Order suggestion document for MongoDB."""

    backtest_id: PydanticObjectId
    ts_code: str
    stock_name: str
    trade_date: str
    settle_date: str
    action: str
    order_price: float
    order_shares: int
    score: float
    up_prob_3d: float
    up_prob_5d: float
    status: str = Field(default="pending")
    actual_price: Optional[float] = None
    actual_shares: Optional[int] = None
    fee: Optional[float] = None
    cash_after: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "order_suggestions"
        indexes = [
            "backtest_id",
            "ts_code",
            "trade_date",
            "status",
        ]
