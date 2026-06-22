"""Shared data structures used across modules."""

from dataclasses import dataclass
from typing import Dict, List, Optional

from pydantic import BaseModel


class ScoredStock(BaseModel):
    """Stock with prediction scores for ranking."""
    # --- 标识 ---
    ts_code: str
    stock_name: str

    # --- 价格 ---
    close: float

    # --- 评分 ---
    raw_score: float = 0.0
    composite_score: float = 0.0
    weighted_score: float = 0.0
    ranking_score: float = 0.0

    # --- 预测概率 ---
    up_prob_3d: float = 0.0
    up_prob_5d: float = 0.0
    up_prob_10d: float = 0.0
    up_prob_20d: float = 0.0
    down_prob_3d: float = 0.0
    down_prob_5d: float = 0.0
    down_prob_10d: float = 0.0
    down_prob_20d: float = 0.0

    # --- 趋势/动量调整 ---
    trend_bonus: float = 0.0
    trend_penalty: float = 0.0
    momentum_bonus: float = 0.0
    momentum_penalty: float = 0.0

    # --- 技术指标 ---
    price_slope: float = 0.0
    price_r_squared: float = 0.0

    # --- 成交量 ---
    volume_ratio: float = 0.0

    # --- 排除标记 ---
    is_excluded: bool = False
    is_explosion_excluded: bool = False
    price_surge_pct: float = 0.0

    # --- 强制卖出标记 (reporting only, set by pipeline) ---
    is_forced_sell: bool = False
    forced_sell_reason: str = ""

    # --- 候选组 (set by pipeline) ---
    candidate_group: str = "base"

    # --- 排名 ---
    rank: int = 0
    rank_improvement: float = 0.0


class PendingOrder(BaseModel):
    """In-memory pending order for settlement tracking."""
    ts_code: str
    stock_name: str
    order_price: float
    order_shares: int
    entry_score: float
    trade_date: str
    settle_date: str
    reason: str = ""
    up_prob_3d: float = 0.0
    up_prob_5d: float = 0.0
    up_prob_10d: float = 0.0
    up_prob_20d: float = 0.0
    candidate_group: str = "base"


class PendingBuy(BaseModel):
    """Reserved buy order awaiting T+1 settlement."""
    ts_code: str
    stock_name: str
    order_shares: int
    order_price: float
    estimated_fee: float
    entry_score: float = 0.0
    atr_at_entry: float = 0.0

    @property
    def reserved_cash(self) -> float:
        return self.order_shares * self.order_price + self.estimated_fee


class MarketDataEmbed(BaseModel):
    """Market regime and ranking statistics for strategy decisions."""
    ranking_high_pct: float = 0.0
    ranking_low_pct: float = 0.0
    top_n_retention_rate: float = 0.0
    top_n_retention_rate_smoothed: float = 0.0
    score_return_corr: float = 0.0
    score_return_corr_smoothed: float = 0.0
    daily_rebalanced_cum: float = 0.0
    rebalanced_ma10_pct: float = 0.0
    rebalanced_ma60_pct: float = 0.0
    market_phase: str = ""
    baseline_vol_multiplier: float = 1.0


@dataclass
class BuyCandidate:
    """A stock recommended by the mode for purchase, with buy reason."""
    stock: ScoredStock
    reason: str = ""


class BuyRecommendation(BaseModel):
    """A stock recommended by strategy, cached in planner for potential purchase."""
    ts_code: str
    stock_name: str
    reason: str
    candidate_group: str = "base"
    added_date: str
    expire_date: str