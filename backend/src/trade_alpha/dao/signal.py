"""SignalResult Document model."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document


class SignalResult(Document):
    """Signal result document for MongoDB."""

    ts_code: str
    trade_date: str
    strategy: str
    action: str
    current_price: float
    target_price: Optional[float] = None
    reason: str
    created_at: Optional[datetime] = None

    class Settings:
        collection = "signal_results"
        indexes = [
            "ts_code",
            "trade_date",
        ]
