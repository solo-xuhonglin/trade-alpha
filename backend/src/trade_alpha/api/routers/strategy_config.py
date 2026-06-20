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
from trade_alpha.logging import get_logger

logger = get_logger("strategy_config_api")


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
        "sell_rank_pct": s.sell_rank_pct,
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
        "ranking_smooth_window": s.ranking_smooth_window,
        "ranking_smooth_alpha": s.ranking_smooth_alpha,
        "score_decline_threshold": s.score_decline_threshold,
        "use_score_decline_filter": s.use_score_decline_filter,
        "full_position_pnl_weight": s.full_position_pnl_weight,
        "use_full_position_sell": s.use_full_position_sell,
        "full_position_threshold": s.full_position_threshold,
        "full_position_days": s.full_position_days,
        "full_position_score_window": s.full_position_score_window,
        "full_position_sell_count": s.full_position_sell_count,
        "use_rank_up_priority": s.use_rank_up_priority,
        "rank_up_window": s.rank_up_window,
        "rank_up_count": s.rank_up_count,
        "rank_up_min_score": s.rank_up_min_score,
        "rank_up_min_improvement_pct": s.rank_up_min_improvement_pct,
        "market_smooth_alpha": s.market_smooth_alpha,
        "market_smooth_window": s.market_smooth_window,
        "top_n_retention_pct": s.top_n_retention_pct,
        "retention_days": s.retention_days,
        "correlation_window": s.correlation_window,
        "use_phase_strategy": s.use_phase_strategy,
        "max_daily_buys": s.max_daily_buys,
        "rotation_bottom_pct": s.rotation_bottom_pct,
        "rotation_rank_min_pct": s.rotation_rank_min_pct,
        "rotation_rank_max_pct": s.rotation_rank_max_pct,
        "rotation_use_reversal_check": s.rotation_use_reversal_check,
        "rotation_was_top_pct": s.rotation_was_top_pct,
        "rotation_pullback_window": s.rotation_pullback_window,
        "rotation_was_top_window": s.rotation_was_top_window,
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
            use_momentum_penalty=request.use_momentum_penalty,
            use_trend_penalty=request.use_trend_penalty,
            ranking_smooth_window=request.ranking_smooth_window,
            ranking_smooth_alpha=request.ranking_smooth_alpha,
            score_decline_threshold=request.score_decline_threshold,
            use_score_decline_filter=request.use_score_decline_filter,
            full_position_pnl_weight=request.full_position_pnl_weight,
            use_full_position_sell=request.use_full_position_sell,
            full_position_threshold=request.full_position_threshold,
            full_position_days=request.full_position_days,
            full_position_score_window=request.full_position_score_window,
            full_position_sell_count=request.full_position_sell_count,
            use_rank_up_priority=request.use_rank_up_priority,
            rank_up_window=request.rank_up_window,
            rank_up_count=request.rank_up_count,
            rank_up_min_score=request.rank_up_min_score,
            rank_up_min_improvement_pct=request.rank_up_min_improvement_pct,
            market_smooth_alpha=request.market_smooth_alpha,
            market_smooth_window=request.market_smooth_window,
            top_n_retention=request.top_n_retention,
            retention_days=request.retention_days,
            correlation_window=request.correlation_window,
            use_phase_strategy=request.use_phase_strategy,
            max_daily_buys=request.max_daily_buys,
            rotation_bottom_threshold=request.rotation_bottom_threshold,
            rotation_rank_min=request.rotation_rank_min,
            rotation_rank_max=request.rotation_rank_max,
            rotation_use_reversal_check=request.rotation_use_reversal_check,
            rotation_was_top_n=request.rotation_was_top_n,
            rotation_pullback_window=request.rotation_pullback_window,
            rotation_was_top_window=request.rotation_was_top_window,
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
            use_momentum_penalty=request.use_momentum_penalty,
            use_trend_penalty=request.use_trend_penalty,
            ranking_smooth_window=request.ranking_smooth_window,
            ranking_smooth_alpha=request.ranking_smooth_alpha,
            score_decline_threshold=request.score_decline_threshold,
            use_score_decline_filter=request.use_score_decline_filter,
            full_position_pnl_weight=request.full_position_pnl_weight,
            use_full_position_sell=request.use_full_position_sell,
            full_position_threshold=request.full_position_threshold,
            full_position_days=request.full_position_days,
            full_position_score_window=request.full_position_score_window,
            full_position_sell_count=request.full_position_sell_count,
            use_rank_up_priority=request.use_rank_up_priority,
            rank_up_window=request.rank_up_window,
            rank_up_count=request.rank_up_count,
            rank_up_min_score=request.rank_up_min_score,
            rank_up_min_improvement_pct=request.rank_up_min_improvement_pct,
            market_smooth_alpha=request.market_smooth_alpha,
            market_smooth_window=request.market_smooth_window,
            top_n_retention=request.top_n_retention,
            retention_days=request.retention_days,
            correlation_window=request.correlation_window,
            use_phase_strategy=request.use_phase_strategy,
            max_daily_buys=request.max_daily_buys,
            rotation_bottom_threshold=request.rotation_bottom_threshold,
            rotation_rank_min=request.rotation_rank_min,
            rotation_rank_max=request.rotation_rank_max,
            rotation_use_reversal_check=request.rotation_use_reversal_check,
            rotation_was_top_n=request.rotation_was_top_n,
            rotation_pullback_window=request.rotation_pullback_window,
            rotation_was_top_window=request.rotation_was_top_window,
        )
        return _strategy_to_dict(s)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Update strategy failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


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
