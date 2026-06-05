"""Shared data structures used across modules."""

from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class ScoredStock:
    """Stock with prediction scores for ranking."""
    ts_code: str
    stock_name: str
    close: float
    score: float
    ranking_score: float = 0.0
    up_prob_3d: float = 0.0
    up_prob_5d: float = 0.0
    up_prob_10d: float = 0.0
    up_prob_20d: float = 0.0
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
    trade_date: str
    settle_date: str
    reason: str = ""
    up_prob_3d: float = 0.0
    up_prob_5d: float = 0.0
    up_prob_10d: float = 0.0
    up_prob_20d: float = 0.0


@dataclass
class PendingBuy:
    """Reserved buy order awaiting T+1 settlement."""
    ts_code: str
    stock_name: str
    order_shares: int
    order_price: float
    estimated_fee: float

    @property
    def reserved_cash(self) -> float:
        return self.order_shares * self.order_price + self.estimated_fee