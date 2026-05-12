"""OrderSuggestion Document model."""

from datetime import datetime
from typing import Optional, Dict
from pydantic import Field
from beanie import Document, PydanticObjectId


class OrderSuggestion(Document):
    """Order suggestion document for MongoDB."""

    execution_result_id: Optional[PydanticObjectId] = None
    ts_code: str
    stock_name: str
    date: str
    action: str
    suggested_price: float
    suggested_shares: int
    signal_strength: float
    position_reason: str
    risk_notes: Optional[str] = None
    prediction_data: Optional[Dict] = None
    account_config_id: PydanticObjectId
    strategy_id: PydanticObjectId
    training_id: PydanticObjectId
    status: str = Field(default="pending")
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "order_suggestions"
        indexes = [
            "ts_code",
            "date",
            "account_config_id",
            "strategy_id",
            "training_id",
            "status",
        ]