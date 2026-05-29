"""TradeCalendar Document model."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document


class TradeCalendar(Document):
    """Trade calendar document for MongoDB."""

    exchange: str
    cal_date: str
    is_open: int
    pretrade_date: Optional[str] = None
    stock_count: Optional[int] = Field(default=None)
    indicator_rate: Optional[float] = Field(default=None)
    updated_at: Optional[datetime] = None

    class Settings:
        name = "trade_calendar"
        indexes = [
            [("cal_date", 1), ("exchange", 1)],
            "cal_date",
        ]