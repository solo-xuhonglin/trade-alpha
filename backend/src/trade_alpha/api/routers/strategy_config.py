"""Strategy API endpoints."""

from fastapi import APIRouter, HTTPException
from beanie import PydanticObjectId
from trade_alpha.api.schemas import (
    StrategyCreateRequest,
    StrategyUpdateRequest,
)
from trade_alpha.strategy.service import (
    create_strategy,
    get_strategy_by_id,
    list_strategies,
    update_strategy,
    delete_strategy,
)


def _strategy_to_dict(s) -> dict:
    return {
        "id": str(s.id),
        "name": s.name,
        "type": s.type,
        "min_order_value": s.min_order_value,
        "stop_loss_pct": s.stop_loss_pct,
        "max_hold_days": s.max_hold_days,
        "min_hold_days": s.min_hold_days,
        "buy_threshold": s.buy_threshold,
        "sell_threshold": s.sell_threshold,
        "max_positions": s.max_positions,
        "max_position_pct": s.max_position_pct,
        "sell_rank_n": s.sell_rank_n,
        "hold_score_threshold": s.hold_score_threshold,
        "use_momentum_boost": s.use_momentum_boost,
        "momentum_window": s.momentum_window,
        "max_momentum_bonus": s.max_momentum_bonus,
        "use_momentum_penalty": s.use_momentum_penalty,
        "use_explosion_filter": s.use_explosion_filter,
        "explosion_price_threshold": s.explosion_price_threshold,
        "explosion_volume_ratio": s.explosion_volume_ratio,
        "explosion_window": s.explosion_window,
        "use_trend_bonus": s.use_trend_bonus,
        "trend_bonus_window": s.trend_bonus_window,
        "trend_bonus_scale": s.trend_bonus_scale,
        "trend_r2_threshold": s.trend_r2_threshold,
        "trend_max_bonus": s.trend_max_bonus,
        "use_trend_penalty": s.use_trend_penalty,
        "use_volatility_penalty": s.use_volatility_penalty,
        "vol_penalty_window": s.vol_penalty_window,
        "vol_range_tolerance": s.vol_range_tolerance,
        "vol_penalty_scale": s.vol_penalty_scale,
        "vol_max_penalty": s.vol_max_penalty,
        "ranking_smooth_window": s.ranking_smooth_window,
        "ranking_smooth_alpha": s.ranking_smooth_alpha,
        "use_full_position_sell": s.use_full_position_sell,
        "full_position_threshold": s.full_position_threshold,
        "full_position_days": s.full_position_days,
        "full_position_score_window": s.full_position_score_window,
        "full_position_sell_count": s.full_position_sell_count,
        "use_acceleration_filter": s.use_acceleration_filter,
        "acceleration_window": s.acceleration_window,
        "acceleration_cum_return": s.acceleration_cum_return,
        "acceleration_up_ratio": s.acceleration_up_ratio,
        "use_rank_up_priority": s.use_rank_up_priority,
        "rank_up_window": s.rank_up_window,
        "rank_up_count": s.rank_up_count,
        "rank_up_min_score": s.rank_up_min_score,
        "rank_up_min_improvement_pct": s.rank_up_min_improvement_pct,
        "market_trend_threshold": s.market_trend_threshold,
        "market_high_score_threshold": s.market_high_score_threshold,
        "market_low_score_threshold": s.market_low_score_threshold,
        "use_market_aware_trading": s.use_market_aware_trading,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
    }


router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("")
async def get_strategies():
    """Get all strategies."""
    strategies = await list_strategies()
    return [_strategy_to_dict(s) for s in strategies]


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str):
    """Get strategy by ID."""
    try:
        obj_id = PydanticObjectId(strategy_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid strategy ID")
    
    s = await get_strategy_by_id(obj_id)
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return _strategy_to_dict(s)


@router.post("")
async def create_strategy_endpoint(request: StrategyCreateRequest):
    """Create a new strategy."""
    try:
        s = await create_strategy(
            name=request.name,
            strategy_type=request.type,
            min_order_value=request.min_order_value,
            stop_loss_pct=request.stop_loss_pct,
            max_hold_days=request.max_hold_days,
            min_hold_days=request.min_hold_days,
            buy_threshold=request.buy_threshold,
            sell_threshold=request.sell_threshold,
            max_positions=request.max_positions,
            max_position_pct=request.max_position_pct,
            sell_rank_n=request.sell_rank_n,
            hold_score_threshold=request.hold_score_threshold,
            use_momentum_boost=request.use_momentum_boost,
            momentum_window=request.momentum_window,
            max_momentum_bonus=request.max_momentum_bonus,
            use_explosion_filter=request.use_explosion_filter,
            explosion_price_threshold=request.explosion_price_threshold,
            explosion_volume_ratio=request.explosion_volume_ratio,
            explosion_window=request.explosion_window,
            use_trend_bonus=request.use_trend_bonus,
            trend_bonus_window=request.trend_bonus_window,
            trend_bonus_scale=request.trend_bonus_scale,
            trend_r2_threshold=request.trend_r2_threshold,
            trend_max_bonus=request.trend_max_bonus,
            use_volatility_penalty=request.use_volatility_penalty,
            vol_penalty_window=request.vol_penalty_window,
            vol_range_tolerance=request.vol_range_tolerance,
            vol_penalty_scale=request.vol_penalty_scale,
            vol_max_penalty=request.vol_max_penalty,
            use_momentum_penalty=request.use_momentum_penalty,
            use_trend_penalty=request.use_trend_penalty,
            ranking_smooth_window=request.ranking_smooth_window,
            ranking_smooth_alpha=request.ranking_smooth_alpha,
            use_full_position_sell=request.use_full_position_sell,
            full_position_threshold=request.full_position_threshold,
            full_position_days=request.full_position_days,
            full_position_score_window=request.full_position_score_window,
            full_position_sell_count=request.full_position_sell_count,
            use_acceleration_filter=request.use_acceleration_filter,
            acceleration_window=request.acceleration_window,
            acceleration_cum_return=request.acceleration_cum_return,
            acceleration_up_ratio=request.acceleration_up_ratio,
            use_rank_up_priority=request.use_rank_up_priority,
            rank_up_window=request.rank_up_window,
            rank_up_count=request.rank_up_count,
            rank_up_min_score=request.rank_up_min_score,
            rank_up_min_improvement_pct=request.rank_up_min_improvement_pct,
            market_trend_threshold=request.market_trend_threshold,
            market_high_score_threshold=request.market_high_score_threshold,
            market_low_score_threshold=request.market_low_score_threshold,
            use_market_aware_trading=request.use_market_aware_trading,
        )
        return _strategy_to_dict(s)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{strategy_id}")
async def update_strategy_endpoint(strategy_id: str, request: StrategyUpdateRequest):
    """Update strategy."""
    try:
        obj_id = PydanticObjectId(strategy_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid strategy ID")
    
    try:
        s = await update_strategy(
            strategy_id=obj_id,
            name=request.name,
            min_order_value=request.min_order_value,
            stop_loss_pct=request.stop_loss_pct,
            max_hold_days=request.max_hold_days,
            min_hold_days=request.min_hold_days,
            buy_threshold=request.buy_threshold,
            sell_threshold=request.sell_threshold,
            max_positions=request.max_positions,
            max_position_pct=request.max_position_pct,
            sell_rank_n=request.sell_rank_n,
            hold_score_threshold=request.hold_score_threshold,
            use_momentum_boost=request.use_momentum_boost,
            momentum_window=request.momentum_window,
            max_momentum_bonus=request.max_momentum_bonus,
            use_explosion_filter=request.use_explosion_filter,
            explosion_price_threshold=request.explosion_price_threshold,
            explosion_volume_ratio=request.explosion_volume_ratio,
            explosion_window=request.explosion_window,
            use_trend_bonus=request.use_trend_bonus,
            trend_bonus_window=request.trend_bonus_window,
            trend_bonus_scale=request.trend_bonus_scale,
            trend_r2_threshold=request.trend_r2_threshold,
            trend_max_bonus=request.trend_max_bonus,
            use_volatility_penalty=request.use_volatility_penalty,
            vol_penalty_window=request.vol_penalty_window,
            vol_range_tolerance=request.vol_range_tolerance,
            vol_penalty_scale=request.vol_penalty_scale,
            vol_max_penalty=request.vol_max_penalty,
            use_momentum_penalty=request.use_momentum_penalty,
            use_trend_penalty=request.use_trend_penalty,
            ranking_smooth_window=request.ranking_smooth_window,
            ranking_smooth_alpha=request.ranking_smooth_alpha,
            use_full_position_sell=request.use_full_position_sell,
            full_position_threshold=request.full_position_threshold,
            full_position_days=request.full_position_days,
            full_position_score_window=request.full_position_score_window,
            full_position_sell_count=request.full_position_sell_count,
            use_acceleration_filter=request.use_acceleration_filter,
            acceleration_window=request.acceleration_window,
            acceleration_cum_return=request.acceleration_cum_return,
            acceleration_up_ratio=request.acceleration_up_ratio,
            use_rank_up_priority=request.use_rank_up_priority,
            rank_up_window=request.rank_up_window,
            rank_up_count=request.rank_up_count,
            rank_up_min_score=request.rank_up_min_score,
            rank_up_min_improvement_pct=request.rank_up_min_improvement_pct,
            market_trend_threshold=request.market_trend_threshold,
            market_high_score_threshold=request.market_high_score_threshold,
            market_low_score_threshold=request.market_low_score_threshold,
            use_market_aware_trading=request.use_market_aware_trading,
        )
        return _strategy_to_dict(s)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=404, detail="Strategy not found")


@router.delete("/{strategy_id}")
async def delete_strategy_endpoint(strategy_id: str):
    """Delete strategy."""
    try:
        obj_id = PydanticObjectId(strategy_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid strategy ID")
    
    deleted = await delete_strategy(obj_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"message": "Strategy deleted"}
