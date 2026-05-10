"""StockDaily Document model."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document


class StockDaily(Document):
    """Stock daily data document for MongoDB."""
    
    ts_code: str
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    vol: float
    amount: float
    ma_5: Optional[float] = None
    ma_10: Optional[float] = None
    ma_20: Optional[float] = None
    ma_60: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    
    class Settings:
        collection = "stock_daily"
        indexes = [
            [("ts_code", 1), ("trade_date", -1)],
        ]
