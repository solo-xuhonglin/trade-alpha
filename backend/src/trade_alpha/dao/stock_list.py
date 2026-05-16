"""StockList Document model."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document


class StockList(Document):
    """Stock list document for MongoDB."""

    ts_code: str
    name: str
    industry: Optional[str] = None
    list_date: Optional[str] = None
    market: Optional[str] = None
    total_mv: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    updated_at: Optional[datetime] = None
    sync_status: Optional[str] = "pending"
    data_count: Optional[int] = None
    latest_date: Optional[str] = None

    class Settings:
        name = "stock_list"
        indexes = [
            "ts_code",
            "market",
            [("total_mv", -1)],
            "sync_status",
        ]
