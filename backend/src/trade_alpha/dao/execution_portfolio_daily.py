"""ExecutionPortfolioDaily Document model."""

from typing import List
from pydantic import Field
from beanie import Document, PydanticObjectId
from trade_alpha.dao.position import Position


class ExecutionPortfolioDaily(Document):
    """Execution portfolio daily snapshot document for MongoDB."""

    backtest_id: PydanticObjectId
    date: str
    cash: float
    positions: List[Position] = Field(default_factory=list)
    market_value: float
    total_value: float
    position_ratio: float
    mode: str = "backtest"

    class Settings:
        name = "execution_portfolio_snapshots"
        indexes = [
            "backtest_id",
            [("backtest_id", 1), ("date", 1)],
        ]
