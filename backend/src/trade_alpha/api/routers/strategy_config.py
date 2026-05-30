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
        "buy_threshold": s.buy_threshold,
        "sell_threshold": s.sell_threshold,
        "max_positions": s.max_positions,
        "max_position_pct": s.max_position_pct,
        "sell_rank_n": s.sell_rank_n,
        "hold_score_threshold": s.hold_score_threshold,
        "use_momentum_boost": s.use_momentum_boost,
        "momentum_window": s.momentum_window,
        "max_momentum_bonus": s.max_momentum_bonus,
        "use_explosion_filter": s.use_explosion_filter,
        "explosion_price_threshold": s.explosion_price_threshold,
        "explosion_volume_ratio": s.explosion_volume_ratio,
        "explosion_window": s.explosion_window,
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
            buy_threshold=request.buy_threshold,
            sell_threshold=request.sell_threshold,
            max_positions=request.max_positions,
            max_position_pct=request.max_position_pct,
            sell_rank_n=request.sell_rank_n,
            hold_score_threshold=request.hold_score_threshold,
            use_momentum_boost=request.use_momentum_boost or False,
            momentum_window=request.momentum_window or 8,
            max_momentum_bonus=request.max_momentum_bonus or 0.1,
            use_explosion_filter=request.use_explosion_filter or False,
            explosion_price_threshold=request.explosion_price_threshold or 0.15,
            explosion_volume_ratio=request.explosion_volume_ratio or 3.0,
            explosion_window=request.explosion_window or 5,
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
