"""ExecutionResult Document model."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from beanie import Document, PydanticObjectId
from pymongo import IndexModel, ASCENDING


class AccountSnapshotEmbed(BaseModel):
    """Embedded account snapshot."""

    name: str
    initial_capital: float
    buy_fee_rate: float
    sell_fee_rate: float
    stamp_tax_rate: float
    min_fee: float


class ModelSnapshotEmbed(BaseModel):
    """Embedded model config snapshot."""

    name: str
    model_type: str
    feature_fields: List[str] = Field(default_factory=list)
    classification_horizons: List[int] = Field(default_factory=list)
    classification_threshold: float


class ExecutionResult(Document):
    """Execution result document for MongoDB."""

    account_config_id: PydanticObjectId
    training_id: PydanticObjectId
    name: str
    mode: str = Field(default="backtest")
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    total_return: float
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    total_fees: float = 0.0
    ts_code: Optional[str] = None
    stock_name: Optional[str] = None
    baseline_return: Optional[float] = None
    excess_return: Optional[float] = None
    baseline_max_drawdown: Optional[float] = None
    baseline_annual_return: Optional[float] = None
    baseline_volatility: Optional[float] = None
    baseline_sharpe_ratio: Optional[float] = None
    annual_return: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    volatility: Optional[float] = None
    avg_hold_days: Optional[float] = None
    account_snapshot: Optional[AccountSnapshotEmbed] = None
    model_snapshot: Optional[ModelSnapshotEmbed] = None
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = Field(default="completed")

    class Settings:
        name = "execution_results"
        indexes = [
            "account_config_id",
            "training_id",
            "ts_code",
            IndexModel("name", unique=True),
        ]
