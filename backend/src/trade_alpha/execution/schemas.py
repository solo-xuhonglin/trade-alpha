"""Execution pipeline schemas - non-persistent data structures."""

from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class ScoredStock:
    """Stock with prediction scores for ranking."""
    ts_code: str
    stock_name: str
    close: float
    up_prob_3d: float
    up_prob_5d: float
    up_prob_10d: float
    score: float
    up_prob_20d: float = 0.0


@dataclass
class PendingOrder:
    """In-memory pending order for settlement tracking."""
    ts_code: str
    stock_name: str
    order_price: float
    order_shares: int
    score: float
    up_prob_3d: float
    up_prob_5d: float
    up_prob_10d: float
    trade_date: str
    settle_date: str
    up_prob_20d: float = 0.0
