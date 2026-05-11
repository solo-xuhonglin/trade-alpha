"""BacktestResult Document model."""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from beanie import Document, PydanticObjectId


class AccountSnapshotEmbed(BaseModel):
    """Embedded account snapshot."""

    name: str
    initial_capital: float
    buy_fee_rate: float
    sell_fee_rate: float
    stamp_tax_rate: float
    min_fee: float


class StrategySnapshotEmbed(BaseModel):
    """Embedded strategy snapshot."""

    name: str
    type: str
    config: Dict[str, Any] = Field(default_factory=dict)


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
    account_snapshot: Optional[AccountSnapshotEmbed] = None
    strategy_snapshot: Optional[StrategySnapshotEmbed] = None
    created_at: Optional[datetime] = None

    class Settings:
        collection = "backtest_results"
        indexes = [
            "ts_code",
            "portfolio_id",
            "strategy_id",
        ]
