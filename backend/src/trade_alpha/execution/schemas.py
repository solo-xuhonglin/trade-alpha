"""Execution pipeline schemas - data structures for execution flow."""

from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime


@dataclass
class StockSignal:
    """Stock trading signal data structure."""
    ts_code: str
    action: str  # "buy" | "sell" | "hold"
    signal_strength: float  # [0, 1]
    current_price: float
    prediction: Dict[str, float]
    reason: str


@dataclass
class OrderSuggestion:
    """Order suggestion data structure."""
    ts_code: str
    stock_name: str
    action: str  # "buy" | "sell" | "hold"
    suggested_price: float
    suggested_shares: int
    signal_strength: float
    position_reason: str
    risk_notes: Optional[str] = None
    prediction_data: Optional[dict] = None
    status: str = "pending"


@dataclass
class ExecutionResult:
    """Execution result data structure."""
    execution_id: str
    mode: str  # "backtest" | "live"
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "running"  # "running" | "completed" | "failed"
    error_message: Optional[str] = None
