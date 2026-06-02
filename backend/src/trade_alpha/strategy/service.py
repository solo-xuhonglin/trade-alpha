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
    min_order_value: float = 5000.0,
    stop_loss_pct: float = -0.1,
    max_hold_days: int = 30,
    min_hold_days: int = 3,
    buy_threshold: float = 0.1,
    sell_threshold: float = -0.1,
    max_positions: Optional[int] = 10,
    max_position_pct: Optional[float] = 0.3,
    sell_rank_n: Optional[int] = 15,
    hold_score_threshold: Optional[float] = 0.05,
    use_momentum_boost: bool = False,
    momentum_window: int = 8,
    max_momentum_bonus: float = 0.1,
    use_explosion_filter: bool = False,
    explosion_price_threshold: float = 0.15,
    explosion_volume_ratio: float = 3.0,
    explosion_window: int = 5,
    use_trend_bonus: bool = False,
    trend_bonus_window: int = 10,
    trend_bonus_scale: float = 0.03,
    trend_r2_threshold: float = 0.30,
    trend_max_bonus: float = 0.05,
    use_volatility_penalty: bool = False,
    vol_penalty_window: int = 10,
    vol_range_tolerance: float = 0.035,
    vol_penalty_scale: float = 0.005,
    vol_max_penalty: float = 0.05,
    ranking_smooth_window: int = 3,
    ranking_smooth_alpha: float = 0.5,
    use_full_position_sell: bool = False,
    full_position_threshold: float = 0.90,
    full_position_days: int = 3,
    full_position_score_window: int = 5,
    full_position_sell_count: int = 1,
    use_acceleration_filter: bool = False,
    acceleration_window: int = 5,
    acceleration_cum_return: float = 0.15,
    acceleration_up_ratio: float = 0.80,
) -> StrategyConfig:
    """Create a new strategy."""
    logger.info(f"Creating strategy: name={name}, type={strategy_type}")

    existing = await StrategyConfig.find_one(StrategyConfig.name == name)
    if existing:
        raise ValueError(f"Strategy name already exists: {name}")

    strategy = StrategyConfig(
        name=name,
        type=strategy_type,
        min_order_value=min_order_value,
        stop_loss_pct=stop_loss_pct,
        max_hold_days=max_hold_days,
        min_hold_days=min_hold_days,
        buy_threshold=buy_threshold,
        sell_threshold=sell_threshold,
        max_positions=max_positions,
        max_position_pct=max_position_pct,
        sell_rank_n=sell_rank_n,
        hold_score_threshold=hold_score_threshold,
        use_momentum_boost=use_momentum_boost,
        momentum_window=momentum_window,
        max_momentum_bonus=max_momentum_bonus,
        use_explosion_filter=use_explosion_filter,
        explosion_price_threshold=explosion_price_threshold,
        explosion_volume_ratio=explosion_volume_ratio,
        explosion_window=explosion_window,
        use_trend_bonus=use_trend_bonus,
        trend_bonus_window=trend_bonus_window,
        trend_bonus_scale=trend_bonus_scale,
        trend_r2_threshold=trend_r2_threshold,
        trend_max_bonus=trend_max_bonus,
        use_volatility_penalty=use_volatility_penalty,
        vol_penalty_window=vol_penalty_window,
        vol_range_tolerance=vol_range_tolerance,
        vol_penalty_scale=vol_penalty_scale,
        vol_max_penalty=vol_max_penalty,
        ranking_smooth_window=ranking_smooth_window,
        ranking_smooth_alpha=ranking_smooth_alpha,
        use_full_position_sell=use_full_position_sell,
        full_position_threshold=full_position_threshold,
        full_position_days=full_position_days,
        full_position_score_window=full_position_score_window,
        full_position_sell_count=full_position_sell_count,
        use_acceleration_filter=use_acceleration_filter,
        acceleration_window=acceleration_window,
        acceleration_cum_return=acceleration_cum_return,
        acceleration_up_ratio=acceleration_up_ratio,
        created_at=datetime.now(timezone.utc),
    )

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
