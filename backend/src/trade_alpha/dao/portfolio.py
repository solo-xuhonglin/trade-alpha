"""AccountConfig Document model."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document, PydanticObjectId


class AccountConfig(Document):
    """Account config document for MongoDB."""

    name: str
    initial_capital: float
    buy_fee_rate: float = Field(default=0.0003)
    sell_fee_rate: float = Field(default=0.0003)
    stamp_tax_rate: float = Field(default=0.001)
    min_fee: float = Field(default=5.0)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Settings:
        collection = "account_configs"
        indexes = [
            "name",
        ]
