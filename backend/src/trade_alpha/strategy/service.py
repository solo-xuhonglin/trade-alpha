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
    sell_rank_n: Optional[int] = None,
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
    top_n_retention: Optional[int] = None,
    retention_days: Optional[int] = None,
    correlation_window: Optional[int] = None,
    use_phase_strategy: Optional[bool] = None,
    phase_crash_threshold: Optional[float] = None,
    phase_recovery_threshold: Optional[float] = None,
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
    sell_rank_n: Optional[int] = None,
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
    top_n_retention: Optional[int] = None,
    retention_days: Optional[int] = None,
    correlation_window: Optional[int] = None,
    use_phase_strategy: Optional[bool] = None,
    phase_crash_threshold: Optional[float] = None,
    phase_recovery_threshold: Optional[float] = None,
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

    if min_order_value is not None:
        strategy.min_order_value = min_order_value
    if stop_loss_pct is not None:
        strategy.stop_loss_pct = stop_loss_pct
    if max_hold_days is not None:
        strategy.max_hold_days = max_hold_days
    if min_hold_days is not None:
        strategy.min_hold_days = min_hold_days
    if buy_threshold is not None:
        strategy.buy_threshold = buy_threshold
    if sell_threshold is not None:
        strategy.sell_threshold = sell_threshold
    if max_positions is not None:
        strategy.max_positions = max_positions
    if max_position_pct is not None:
        strategy.max_position_pct = max_position_pct
    if sell_rank_n is not None:
        strategy.sell_rank_n = sell_rank_n
    if hold_score_threshold is not None:
        strategy.hold_score_threshold = hold_score_threshold
    if use_momentum_boost is not None:
        strategy.use_momentum_boost = use_momentum_boost
    if momentum_window is not None:
        strategy.momentum_window = momentum_window
    if max_momentum_bonus is not None:
        strategy.max_momentum_bonus = max_momentum_bonus
    if use_explosion_filter is not None:
        strategy.use_explosion_filter = use_explosion_filter
    if explosion_price_threshold is not None:
        strategy.explosion_price_threshold = explosion_price_threshold
    if explosion_volume_ratio is not None:
        strategy.explosion_volume_ratio = explosion_volume_ratio
    if explosion_window is not None:
        strategy.explosion_window = explosion_window
    if use_trend_bonus is not None:
        strategy.use_trend_bonus = use_trend_bonus
    if trend_bonus_window is not None:
        strategy.trend_bonus_window = trend_bonus_window
    if trend_bonus_scale is not None:
        strategy.trend_bonus_scale = trend_bonus_scale
    if trend_r2_threshold is not None:
        strategy.trend_r2_threshold = trend_r2_threshold
    if trend_max_bonus is not None:
        strategy.trend_max_bonus = trend_max_bonus
    if use_volatility_penalty is not None:
        strategy.use_volatility_penalty = use_volatility_penalty
    if vol_penalty_window is not None:
        strategy.vol_penalty_window = vol_penalty_window
    if vol_range_tolerance is not None:
        strategy.vol_range_tolerance = vol_range_tolerance
    if vol_penalty_scale is not None:
        strategy.vol_penalty_scale = vol_penalty_scale
    if vol_max_penalty is not None:
        strategy.vol_max_penalty = vol_max_penalty
    if use_momentum_penalty is not None:
        strategy.use_momentum_penalty = use_momentum_penalty
    if use_trend_penalty is not None:
        strategy.use_trend_penalty = use_trend_penalty
    if ranking_smooth_window is not None:
        strategy.ranking_smooth_window = ranking_smooth_window
    if ranking_smooth_alpha is not None:
        strategy.ranking_smooth_alpha = ranking_smooth_alpha
    if use_full_position_sell is not None:
        strategy.use_full_position_sell = use_full_position_sell
    if full_position_threshold is not None:
        strategy.full_position_threshold = full_position_threshold
    if full_position_days is not None:
        strategy.full_position_days = full_position_days
    if full_position_score_window is not None:
        strategy.full_position_score_window = full_position_score_window
    if full_position_sell_count is not None:
        strategy.full_position_sell_count = full_position_sell_count
    if use_acceleration_filter is not None:
        strategy.use_acceleration_filter = use_acceleration_filter
    if acceleration_window is not None:
        strategy.acceleration_window = acceleration_window
    if acceleration_cum_return is not None:
        strategy.acceleration_cum_return = acceleration_cum_return
    if acceleration_up_ratio is not None:
        strategy.acceleration_up_ratio = acceleration_up_ratio
    if use_rank_up_priority is not None:
        strategy.use_rank_up_priority = use_rank_up_priority
    if rank_up_window is not None:
        strategy.rank_up_window = rank_up_window
    if rank_up_count is not None:
        strategy.rank_up_count = rank_up_count
    if rank_up_min_score is not None:
        strategy.rank_up_min_score = rank_up_min_score
    if rank_up_min_improvement_pct is not None:
        strategy.rank_up_min_improvement_pct = rank_up_min_improvement_pct
    if market_smooth_alpha is not None:
        strategy.market_smooth_alpha = market_smooth_alpha
    if market_smooth_window is not None:
        strategy.market_smooth_window = market_smooth_window
    if top_n_retention is not None:
        strategy.top_n_retention = top_n_retention
    if retention_days is not None:
        strategy.retention_days = retention_days
    if correlation_window is not None:
        strategy.correlation_window = correlation_window
    if use_phase_strategy is not None:
        strategy.use_phase_strategy = use_phase_strategy
    if phase_crash_threshold is not None:
        strategy.phase_crash_threshold = phase_crash_threshold
    if phase_recovery_threshold is not None:
        strategy.phase_recovery_threshold = phase_recovery_threshold

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
