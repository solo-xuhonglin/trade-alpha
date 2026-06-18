"""StockListHistory Document model — historical market cap data."""

from typing import Optional
from beanie import Document


class StockListHistory(Document):
    """Historical market cap snapshot per stock per trade date."""

    ts_code: str
    trade_date: str
    total_mv: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None

    class Settings:
        name = "stock_list_history"
        indexes = [
            [("ts_code", 1), ("trade_date", 1)],
            "trade_date",
        ]
