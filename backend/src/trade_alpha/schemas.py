"""Shared data structures used across modules."""

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
    score: float
    ranking_score: float = 0.0
    is_excluded: bool = False
    trend_bonus: float = 0.0
    vol_penalty: float = 0.0
    price_slope: float = 0.0
    price_r_squared: float = 0.0
    price_avg_range: float = 0.0


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
    trade_date: str
    settle_date: str
    reason: str = ""
