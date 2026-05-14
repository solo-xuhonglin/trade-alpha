"""ExecutionPortfolioDaily Document model."""

from typing import List
from pydantic import Field
from beanie import Document, PydanticObjectId
from trade_alpha.dao.position import PositionEmbed


class ExecutionPortfolioDaily(Document):
    """Execution portfolio daily snapshot document for MongoDB."""

    backtest_id: PydanticObjectId
    date: str
    cash: float
    positions: List[PositionEmbed] = Field(default_factory=list)
    total_market_value: float = 0.0
    total_value: float = 0.0
    day_return: float = 0.0
    mode: str = Field(default="backtest")
    baseline_value: float = 0.0
    baseline_hold_days: int = 0

    class Settings:
        name = "execution_portfolio_snapshots"
        indexes = [
            "backtest_id",
            [("backtest_id", 1), ("date", 1)],
        ]
