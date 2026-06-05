"""LiveOrderSuggestion Document model for live suggestion stocks."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document


class LiveOrderSuggestion(Document):
    """Live suggestion stock document (strategy-filtered stocks)."""

    ts_code: str
    stock_name: str
    trade_date: str

    # Score system
    raw_score: float
    composite_score: float
    ranking_score: float = 0.0
    rank: int = 0

    # Probability
    up_prob_3d: float = 0.0
    up_prob_5d: float = 0.0
    up_prob_10d: float = 0.0
    up_prob_20d: float = 0.0

    # Bonus/penalty details
    trend_bonus: float = 0.0
    vol_penalty: float = 0.0
    momentum_bonus: float = 0.0

    # Exclusion
    is_excluded: bool = False
    excluded_reason: Optional[str] = None

    # Status
    reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "live_order_suggestions"
        indexes = [
            "ts_code",
            "trade_date",
            [("ts_code", 1), ("trade_date", 1)],  # unique compound -> dedup
        ]