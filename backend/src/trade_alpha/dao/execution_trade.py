"""ExecutionTrade Document model."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document, PydanticObjectId


class ExecutionTrade(Document):
    """Execution trade document for MongoDB."""

    backtest_id: PydanticObjectId
    ts_code: str
    trade_date: str
    action: str
    filled_price: float
    order_price: float
    shares: int
    fee: float
    cash_after: float
    reason: Optional[str] = None
    entry_score: Optional[float] = None
    up_prob_3d: Optional[float] = None
    up_prob_5d: Optional[float] = None
    up_prob_10d: Optional[float] = None
    up_prob_20d: Optional[float] = None
    pnl_amount: Optional[float] = None
    pnl_pct: Optional[float] = None
    candidate_group: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    mode: str = Field(default="backtest")
    status: str = Field(default="filled")  # "filled" or "cancelled"

    class Settings:
        name = "execution_trades"
        indexes = [
            "backtest_id",
            "ts_code",
            "trade_date",
        ]
