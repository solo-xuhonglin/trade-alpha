"""BacktestPortfolioDaily Document model."""

from typing import List
from pydantic import Field
from beanie import Document, PydanticObjectId
from trade_alpha.dao.position import Position


class BacktestPortfolioDaily(Document):
    """Backtest portfolio daily snapshot document for MongoDB."""

    backtest_id: PydanticObjectId
    date: str
    cash: float
    positions: List[Position] = Field(default_factory=list)
    market_value: float
    total_value: float
    position_ratio: float

    class Settings:
        name = "backtest_portfolio_daily"
        indexes = [
            "backtest_id",
            [("backtest_id", 1), ("date", 1)],
        ]
