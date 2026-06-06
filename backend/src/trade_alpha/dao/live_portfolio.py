"""LivePortfolio Document model for manual position management."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from beanie import Document


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
    """Portfolio document holding cash, positions and fee settings.

    Only one document exists in the live_portfolio collection.
    """

    total_cash: float = 0.0
    buy_fee_rate: float = 0.0003
    sell_fee_rate: float = 0.0003
    stamp_tax_rate: float = 0.001
    min_fee: float = 5.0
    positions: List[LivePositionEmbed] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "live_portfolio"