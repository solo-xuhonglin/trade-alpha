"""BacktestResult Document model."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document, PydanticObjectId


class BacktestResult(Document):
    """Backtest result document for MongoDB."""

    portfolio_id: Optional[PydanticObjectId] = None
    strategy_id: Optional[PydanticObjectId] = None
    training_id: Optional[PydanticObjectId] = None
    ts_code: str
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    total_return: float
    annual_return: float
    benchmark_return: float = Field(default=0.0)
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    total_fees: float
    created_at: Optional[datetime] = None

    class Settings:
        collection = "backtest_results"
        indexes = [
            "ts_code",
            "portfolio_id",
            "strategy_id",
        ]
