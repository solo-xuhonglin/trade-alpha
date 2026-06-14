"""LiveDailyStockScore Document model for daily stock scoring/ranking."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document


class LiveDailyStockScore(Document):
    """Per-stock-per-day scoring record. Upserted by (ts_code, trade_date)."""

    ts_code: str
    trade_date: str
    stock_name: Optional[str] = None
    rank: int = 0
    raw_score: float = 0.0
    composite_score: float = 0.0
    ranking_score: float = 0.0
    up_prob_3d: float = 0.0
    up_prob_5d: float = 0.0
    up_prob_10d: float = 0.0
    trend_bonus: float = 0.0
    vol_penalty: float = 0.0
    momentum_bonus: float = 0.0
    momentum_penalty: float = 0.0
    trend_penalty: float = 0.0
    order_price: float = 0.0
    order_shares: int = 0
    is_excluded: bool = False
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "live_daily_stock_score"
        indexes = [
            [("ts_code", 1), ("trade_date", 1)],
            [("trade_date", -1), ("rank", 1)],
        ]