"""LivePortfolio Document model for manual position management."""

from datetime import datetime
from typing import List
from pydantic import BaseModel, Field, field_validator
from beanie import Document, Indexed


class LivePositionEmbed(BaseModel):
    """Embedded position record within LivePortfolio."""

    id: str
    ts_code: str
    stock_name: str
    shares: int
    cost_price: float
    total_cost: float
    created_at: datetime
    updated_at: datetime


class LivePortfolio(Document):
    """Portfolio document holding stock positions.

    Named portfolio documents; use name field to distinguish instances.
    """

    name: str = Indexed(unique=True)
    positions: List[LivePositionEmbed] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "live_portfolio"