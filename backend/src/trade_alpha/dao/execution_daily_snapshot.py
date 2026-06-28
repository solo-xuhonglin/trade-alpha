"""ExecutionDailySnapshot Document model."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from beanie import Document, PydanticObjectId
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.schemas import ScoredStock


class PlannerCandidateEmbed(BaseModel):
    """Planner daily candidate with priority breakdown."""
    ts_code: str
    stock_name: str = ""
    ranking_score: float = 0.0
    composite_score: float = 0.0
    rank: int = 0
    norm_score: float = 0.0
    norm_prob: float = 0.0
    norm_ri: float = 0.0
    norm_rank: float = 0.0
    final_priority: float = 0.0
    reason: str = ""
    target_price: float = 0.0
    cache_days: int = 0
    is_ordered: bool = False


class ExecutionDailySnapshot(Document):
    """Daily backtest snapshot with predictions."""

    backtest_id: PydanticObjectId
    date: str
    cash: float
    positions: List[PositionEmbed] = Field(default_factory=list)
    total_market_value: float = 0.0
    total_value: float = 0.0
    day_return: float = 0.0
    mode: str = Field(default="backtest")
    baseline_value: float = 0.0
    baseline_hold_days: int = 0
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
    position_pct: float = 0.0
    predictions: Dict[str, ScoredStock] = Field(default_factory=dict)
    planner_candidates: List[PlannerCandidateEmbed] = Field(default_factory=list)

    class Settings:
        name = "execution_daily_snapshots"
        indexes = [
            "backtest_id",
            [("backtest_id", 1), ("date", 1)],
        ]
