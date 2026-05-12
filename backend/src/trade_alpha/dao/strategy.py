"""StrategyConfig Document model."""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import Field
from beanie import Document


class StrategyConfig(Document):
    """Strategy config document for MongoDB."""

    name: str
    type: str = Field(default="price")
    config: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Settings:
        name = "strategy_configs"
        indexes = [
            "name",
        ]
