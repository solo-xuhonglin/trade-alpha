"""Strategy service module."""

from datetime import datetime, timezone
from typing import Optional, List
from beanie import PydanticObjectId
from trade_alpha.dao import StrategyConfig
from trade_alpha.logging import get_logger

logger = get_logger("strategy_service")


async def create_strategy(
    name: str,
    strategy_type: str,
    min_order_value: Optional[float] = None,
    stop_loss_pct: Optional[float] = None,
    max_hold_days: Optional[int] = None,
    min_hold_days: Optional[int] = None,
    buy_threshold: Optional[float] = None,
    sell_threshold: Optional[float] = None,
    max_positions: Optional[int] = None,
    max_position_pct: Optional[float] = None,
    sell_rank_pct: Optional[float] = None,
    hold_score_threshold: Optional[float] = None,
    use_momentum_boost: Optional[bool] = None,
    momentum_window: Optional[int] = None,
    max_momentum_bonus: Optional[float] = None,
    use_explosion_filter: Optional[bool] = None,
    explosion_price_threshold: Optional[float] = None,
    explosion_volume_ratio: Optional[float] = None,
    explosion_window: Optional[int] = None,
    use_trend_bonus: Optional[bool] = None,
    trend_bonus_window: Optional[int] = None,
    trend_bonus_scale: Optional[float] = None,
    trend_r2_threshold: Optional[float] = None,
    trend_max_bonus: Optional[float] = None,
    use_volatility_penalty: Optional[bool] = None,
    vol_penalty_window: Optional[int] = None,
    use_momentum_penalty: Optional[bool] = None,
    use_trend_penalty: Optional[bool] = None,
    vol_range_tolerance: Optional[float] = None,
    vol_penalty_scale: Optional[float] = None,
    vol_max_penalty: Optional[float] = None,
    ranking_smooth_window: Optional[int] = None,
    ranking_smooth_alpha: Optional[float] = None,
    score_decline_threshold: Optional[float] = None,
    use_score_decline_filter: Optional[bool] = None,
    full_position_pnl_weight: Optional[float] = None,
    use_full_position_sell: Optional[bool] = None,
    full_position_threshold: Optional[float] = None,
    full_position_days: Optional[int] = None,
    full_position_score_window: Optional[int] = None,
    full_position_sell_count: Optional[int] = None,
    use_acceleration_filter: Optional[bool] = None,
    acceleration_window: Optional[int] = None,
    acceleration_cum_return: Optional[float] = None,
    acceleration_up_ratio: Optional[float] = None,
    use_rank_up_priority: Optional[bool] = None,
    rank_up_window: Optional[int] = None,
    rank_up_count: Optional[int] = None,
    rank_up_min_score: Optional[float] = None,
    rank_up_min_improvement_pct: Optional[float] = None,
    market_smooth_alpha: Optional[float] = None,
    market_smooth_window: Optional[int] = None,
    top_n_retention_pct: Optional[float] = None,
    retention_days: Optional[int] = None,
    correlation_window: Optional[int] = None,
    use_phase_strategy: Optional[bool] = None,
    atr_stop_multiplier: Optional[float] = None,
    atr_trail_rate: Optional[float] = None,
    max_daily_buys: Optional[int] = None,
    rotation_bottom_pct: Optional[float] = None,
    rotation_rank_min_pct: Optional[float] = None,
    rotation_rank_max_pct: Optional[float] = None,
    rotation_use_reversal_check: Optional[bool] = None,
    rotation_was_top_pct: Optional[float] = None,
    rotation_pullback_window: Optional[int] = None,
    rotation_was_top_window: Optional[int] = None,
    sel_trend_slope_weight: Optional[float] = None,
    sel_trend_arrangement_weight: Optional[float] = None,
    sel_close_position_20_weight: Optional[float] = None,
    sel_close_position_60_weight: Optional[float] = None,
    sel_bias_20_weight: Optional[float] = None,
    sel_bias_60_weight: Optional[float] = None,
    sel_atr_14_weight: Optional[float] = None,
    sel_log_mv_weight: Optional[float] = None,
    sel_rank_rise_weight: Optional[float] = None,
    sel_ewma_alpha: Optional[float] = None,
    use_weighted_score: Optional[bool] = None,
    weighted_score_factor: Optional[float] = None,
    use_hold_protection: Optional[bool] = None,
) -> StrategyConfig:
    """Create a new strategy."""
    logger.info(f"Creating strategy: name={name}, type={strategy_type}")

    existing = await StrategyConfig.find_one(StrategyConfig.name == name)
    if existing:
        raise ValueError(f"Strategy name already exists: {name}")

    # Include only non-None fields so DAO model defaults apply
    field_names = StrategyConfig.model_fields.keys()
    kwargs = {k: v for k, v in locals().items()
              if k in field_names and v is not None}
    kwargs["type"] = strategy_type  # map param name to DAO field name
    kwargs["created_at"] = datetime.now(timezone.utc)

    strategy = StrategyConfig(**kwargs)

    await strategy.insert()
    logger.info(f"Strategy created: id={strategy.id}")
    return strategy


async def get_strategy_by_id(strategy_id: PydanticObjectId) -> Optional[StrategyConfig]:
    """Get strategy by ID."""
    return await StrategyConfig.get(strategy_id)


async def get_strategy_by_name(name: str) -> Optional[StrategyConfig]:
    """Get strategy by name."""
    return await StrategyConfig.find_one(StrategyConfig.name == name)


async def list_strategies() -> List[StrategyConfig]:
    """List all strategies."""
    return await StrategyConfig.find_all().sort(-StrategyConfig.created_at).to_list()


async def update_strategy(
    strategy_id: PydanticObjectId,
    name: Optional[str] = None,
    min_order_value: Optional[float] = None,
    stop_loss_pct: Optional[float] = None,
    max_hold_days: Optional[int] = None,
    min_hold_days: Optional[int] = None,
    buy_threshold: Optional[float] = None,
    sell_threshold: Optional[float] = None,
    max_positions: Optional[int] = None,
    max_position_pct: Optional[float] = None,
    sell_rank_pct: Optional[float] = None,
    hold_score_threshold: Optional[float] = None,
    use_momentum_boost: Optional[bool] = None,
    momentum_window: Optional[int] = None,
    max_momentum_bonus: Optional[float] = None,
    use_explosion_filter: Optional[bool] = None,
    explosion_price_threshold: Optional[float] = None,
    explosion_volume_ratio: Optional[float] = None,
    explosion_window: Optional[int] = None,
    use_trend_bonus: Optional[bool] = None,
    trend_bonus_window: Optional[int] = None,
    trend_bonus_scale: Optional[float] = None,
    trend_r2_threshold: Optional[float] = None,
    trend_max_bonus: Optional[float] = None,
    use_volatility_penalty: Optional[bool] = None,
    vol_penalty_window: Optional[int] = None,
    use_momentum_penalty: Optional[bool] = None,
    use_trend_penalty: Optional[bool] = None,
    vol_range_tolerance: Optional[float] = None,
    vol_penalty_scale: Optional[float] = None,
    vol_max_penalty: Optional[float] = None,
    ranking_smooth_window: Optional[int] = None,
    ranking_smooth_alpha: Optional[float] = None,
    score_decline_threshold: Optional[float] = None,
    use_score_decline_filter: Optional[bool] = None,
    full_position_pnl_weight: Optional[float] = None,
    use_full_position_sell: Optional[bool] = None,
    full_position_threshold: Optional[float] = None,
    full_position_days: Optional[int] = None,
    full_position_score_window: Optional[int] = None,
    full_position_sell_count: Optional[int] = None,
    use_acceleration_filter: Optional[bool] = None,
    acceleration_window: Optional[int] = None,
    acceleration_cum_return: Optional[float] = None,
    acceleration_up_ratio: Optional[float] = None,
    use_rank_up_priority: Optional[bool] = None,
    rank_up_window: Optional[int] = None,
    rank_up_count: Optional[int] = None,
    rank_up_min_score: Optional[float] = None,
    rank_up_min_improvement_pct: Optional[float] = None,
    market_smooth_alpha: Optional[float] = None,
    market_smooth_window: Optional[int] = None,
    top_n_retention_pct: Optional[float] = None,
    retention_days: Optional[int] = None,
    correlation_window: Optional[int] = None,
    use_phase_strategy: Optional[bool] = None,
    atr_stop_multiplier: Optional[float] = None,
    atr_trail_rate: Optional[float] = None,
    max_daily_buys: Optional[int] = None,
    rotation_bottom_pct: Optional[float] = None,
    rotation_rank_min_pct: Optional[float] = None,
    rotation_rank_max_pct: Optional[float] = None,
    rotation_use_reversal_check: Optional[bool] = None,
    rotation_was_top_pct: Optional[float] = None,
    rotation_pullback_window: Optional[int] = None,
    rotation_was_top_window: Optional[int] = None,
    sel_trend_slope_weight: Optional[float] = None,
    sel_trend_arrangement_weight: Optional[float] = None,
    sel_close_position_20_weight: Optional[float] = None,
    sel_close_position_60_weight: Optional[float] = None,
    sel_bias_20_weight: Optional[float] = None,
    sel_bias_60_weight: Optional[float] = None,
    sel_atr_14_weight: Optional[float] = None,
    sel_log_mv_weight: Optional[float] = None,
    sel_rank_rise_weight: Optional[float] = None,
    sel_ewma_alpha: Optional[float] = None,
    use_weighted_score: Optional[bool] = None,
    weighted_score_factor: Optional[float] = None,
    use_hold_protection: Optional[bool] = None,
) -> Optional[StrategyConfig]:
    """Update strategy."""
    strategy = await StrategyConfig.get(strategy_id)
    if not strategy:
        return None

    if name is not None:
        existing = await StrategyConfig.find_one(StrategyConfig.name == name)
        if existing and existing.id != strategy_id:
            raise ValueError(f"Strategy name already exists: {name}")
        strategy.name = name

    # Auto-assign all matching fields
    field_names = StrategyConfig.model_fields.keys()
    for f in field_names:
        val = locals().get(f)
        if val is not None and f != "name":
            setattr(strategy, f, val)

    strategy.updated_at = datetime.now(timezone.utc)
    await strategy.save()
    logger.info(f"Strategy updated: id={strategy_id}")
    return strategy


async def delete_strategy(strategy_id: PydanticObjectId) -> bool:
    """Delete strategy."""
    strategy = await StrategyConfig.get(strategy_id)
    if not strategy:
        return False

    await strategy.delete()
    logger.info(f"Strategy deleted: id={strategy_id}")
    return True
