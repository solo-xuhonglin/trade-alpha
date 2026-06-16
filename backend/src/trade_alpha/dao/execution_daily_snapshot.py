"""ExecutionDailySnapshot Document model."""

from typing import Dict, List, Optional
from pydantic import Field
from beanie import Document, PydanticObjectId
from trade_alpha.dao.position import PositionEmbed
from trade_alpha.schemas import ScoredStock


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
    ranking_median: float = 0.0
    ranking_high_pct: float = 0.0
    ranking_low_pct: float = 0.0
    ranking_regime: str = ""
    top_n_retention_rate: float = 0.0
    top_n_retention_rate_smoothed: float = 0.0
    score_return_corr: float = 0.0
    score_return_corr_smoothed: float = 0.0
    daily_rebalanced_cum: float = 0.0
    position_multiplier: float = 1.0
    buy_threshold_multiplier: float = 1.0
    market_phase: str = ""
    position_pct: float = 0.0
    predictions: Dict[str, ScoredStock] = Field(default_factory=dict)

    class Settings:
        name = "execution_daily_snapshots"
        indexes = [
            "backtest_id",
            [("backtest_id", 1), ("date", 1)],
        ]
