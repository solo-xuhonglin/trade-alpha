from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


@dataclass
class StockSignal:
    ts_code: str
    action: str
    signal_strength: float
    current_price: float
    prediction: Dict[str, float]
    reason: str


@dataclass
class OrderSuggestion:
    ts_code: str
    stock_name: str
    action: str
    suggested_price: float
    suggested_shares: int
    signal_strength: float
    position_reason: str
    risk_notes: Optional[str] = None
    prediction_data: Optional[dict] = None
    status: str = field(default="pending")


@dataclass
class ExecutionResult:
    execution_id: str
    mode: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = field(default="running")
    error_message: Optional[str] = None
