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
    is_active_for_backtest: Optional[bool] = False

    @staticmethod
    async def get_top_n_ts_codes(n: int) -> list[str]:
        """Get ts_codes of top N stocks by total_mv descending."""
        stocks = await StockList.find_all().sort(-StockList.total_mv).limit(n).to_list()
        return [s.ts_code for s in stocks]

    @staticmethod
    async def get_all_ts_codes() -> set[str]:
        """Get all existing ts_codes as a set."""
        stocks = await StockList.find_all().to_list()
        return {s.ts_code for s in stocks}

    class Settings:
        name = "stock_list"
        indexes = [
            "ts_code",
            "market",
            [("total_mv", -1)],
            "sync_status",
            "is_active_for_backtest",
        ]
