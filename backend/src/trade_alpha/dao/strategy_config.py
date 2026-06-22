"""StrategyConfig Document model."""

from datetime import datetime
from typing import Optional
from pydantic import Field
from beanie import Document


class StrategyConfig(Document):
    """Strategy config document for MongoDB."""

    name: str
    type: str = Field(default="multi")
    min_order_value: float = 50000.0
    stop_loss_pct: float = -0.1
    max_hold_days: int = 180
    min_hold_days: int = 5
    buy_threshold: float = 0.3
    sell_threshold: float = -0.05
    max_positions: Optional[int] = 6
    max_position_pct: Optional[float] = 0.2
    sell_rank_pct: float = 0.15
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
    full_position_score_window: int = 15
    full_position_sell_count: int = 1
    use_rank_up_priority: bool = False
    rank_up_window: int = 3
    rank_up_count: int = 1
    rank_up_min_score: float = -0.1
    rank_up_min_improvement_pct: float = 0.15
    ranking_smooth_window: int = 5
    ranking_smooth_alpha: float = 0.3
    score_decline_threshold: float = 0.05
    use_score_decline_filter: bool = False
    full_position_pnl_weight: float = 0.5
    market_smooth_window: int = 3
    market_smooth_alpha: float = 0.3
    top_n_retention_pct: float = 0.20
    retention_days: int = 5
    correlation_window: int = 5
    use_phase_strategy: bool = True
    atr_stop_multiplier: float = 3.0
    atr_trail_rate: float = 0.5
    max_daily_buys: int = 2
    rotation_bottom_pct: float = 0.60
    rotation_rank_min_pct: float = 0.30
    rotation_rank_max_pct: float = 0.70
    rotation_use_reversal_check: bool = True
    rotation_was_top_pct: float = 0.15
    rotation_pullback_window: int = 5
    rotation_was_top_window: int = 60

    # ── 选股参数 ──
    sel_trend_slope_weight: float = 1.0
    sel_trend_arrangement_weight: float = 1.0
    sel_close_position_20_weight: float = 1.0
    sel_close_position_60_weight: float = 1.0
    sel_bias_20_weight: float = 1.0
    sel_bias_60_weight: float = 1.0
    sel_atr_14_weight: float = 0.3
    sel_log_mv_weight: float = 1.0
    sel_rank_rise_weight: float = 0.2
    sel_ewma_alpha: float = 0.7

    # ── 分数加权 ──
    use_weighted_score: bool = False
    weighted_score_factor: float = 0.2

    # ── 持仓保护 ──
    use_hold_protection: bool = False

    # ── 买入执行 ──
    buy_cache_days: int = 3
    buy_price_close_weight: float = 0.3
    buy_price_ma5_weight: float = 0.3
    buy_price_ma10_weight: float = 0.4
    buy_price_buffer_pct: float = 0.01
    buy_score_weight: float = 1.0
    buy_prob_weight: float = 1.0

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Settings:
        name = "strategy_configs"
        indexes = [
            "name",
        ]
