"""StrategyConfig Document model."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document


class StrategyConfig(Document):
    """Strategy config document for MongoDB."""

    name: str
    type: str = Field(default="single")
    min_order_value: float = 5000.0
    stop_loss_pct: float = -0.1
    max_hold_days: int = 30
    buy_threshold: float = 0.1
    sell_threshold: float = -0.1
    max_positions: Optional[int] = 10
    max_position_pct: Optional[float] = 0.3
    sell_rank_n: Optional[int] = 15
    hold_score_threshold: Optional[float] = 0.05
    use_momentum_boost: bool = False
    momentum_window: int = 8
    max_momentum_bonus: float = 0.1
    use_explosion_filter: bool = False
    explosion_price_threshold: float = 0.15
    explosion_volume_ratio: float = 3.0
    explosion_window: int = 5
    use_trend_bonus: bool = False
    trend_bonus_window: int = 10
    trend_bonus_scale: float = 0.03
    trend_r2_threshold: float = 0.30
    trend_max_bonus: float = 0.05
    use_volatility_penalty: bool = False
    vol_penalty_window: int = 10
    vol_range_tolerance: float = 0.035
    vol_penalty_scale: float = 0.005
    vol_max_penalty: float = 0.05
    use_full_position_sell: bool = False
    full_position_threshold: float = 0.90
    full_position_days: int = 3
    full_position_score_window: int = 5
    full_position_sell_count: int = 1
    use_acceleration_filter: bool = False
    acceleration_window: int = 5
    acceleration_cum_return: float = 0.15
    acceleration_up_ratio: float = 0.80
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Settings:
        name = "strategy_configs"
        indexes = [
            "name",
        ]
