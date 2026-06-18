"""StrategyConfig Document model."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document


class StrategyConfig(Document):
    """Strategy config document for MongoDB."""

    name: str
    type: str = Field(default="multi")
    min_order_value: float = 5000.0
    stop_loss_pct: float = -0.1
    max_hold_days: int = 120
    min_hold_days: int = 5
    buy_threshold: float = 0.2
    sell_threshold: float = -0.01
    max_positions: Optional[int] = 10
    max_position_pct: Optional[float] = 0.1
    sell_rank_n: Optional[int] = 15
    hold_score_threshold: Optional[float] = 0.1
    use_momentum_boost: bool = False
    momentum_window: int = 12
    max_momentum_bonus: float = 0.15
    use_momentum_penalty: bool = False
    use_explosion_filter: bool = False
    explosion_price_threshold: float = 0.08
    explosion_volume_ratio: float = 3.0
    explosion_window: int = 5
    use_trend_bonus: bool = False
    trend_bonus_window: int = 15
    trend_bonus_scale: float = 0.03
    trend_r2_threshold: float = 0.30
    trend_max_bonus: float = 0.1
    use_trend_penalty: bool = False
    use_full_position_sell: bool = False
    full_position_threshold: float = 0.90
    full_position_days: int = 5
    full_position_score_window: int = 10
    full_position_sell_count: int = 1
    use_rank_up_priority: bool = False
    rank_up_window: int = 5
    rank_up_count: int = 3
    rank_up_min_score: float = 0.1
    rank_up_min_improvement_pct: float = 0.20
    ranking_smooth_window: int = 5
    ranking_smooth_alpha: float = 0.3
    score_decline_threshold: float = 0.05
    use_score_decline_filter: bool = False
    full_position_pnl_weight: float = 0.5
    market_smooth_window: int = 5
    market_smooth_alpha: float = 0.3
    top_n_retention: int = 20
    retention_days: int = 5
    correlation_window: int = 5
    use_phase_strategy: bool = True
    phase_crash_threshold: float = -0.06
    phase_recovery_threshold: float = -0.03
    baseline_vol_window: int = 20
    baseline_vol_ref_multiplier: int = 3
    # Rotation mode params
    rotation_bottom_threshold: int = 60
    rotation_rank_min: int = 45
    rotation_rank_max: int = 75
    rotation_use_reversal_check: bool = True
    rotation_was_top_n: int = 15
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Settings:
        name = "strategy_configs"
        indexes = [
            "name",
        ]
