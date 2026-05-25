"""StrategyConfig Document model."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document


class StrategyConfig(Document):
    """Strategy config document for MongoDB."""

    name: str
    type: str = Field(default="single")
    min_order_value: float = 5000.0
    stop_loss_pct: float = -0.1
    max_hold_days: int = 30
    buy_threshold: float = 0.1
    sell_threshold: float = -0.1
    max_positions: Optional[int] = 10
    max_position_pct: Optional[float] = 0.3
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Settings:
        name = "strategy_configs"
        indexes = [
            "name",
        ]
