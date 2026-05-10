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

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("")
async def get_strategies():
    """Get all strategies."""
    return await list_strategies()


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str):
    """Get strategy by ID."""
    try:
        obj_id = PydanticObjectId(strategy_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid strategy ID")
    
    strategy = await get_strategy_by_id(obj_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy


@router.post("")
async def create_strategy_endpoint(request: StrategyCreateRequest):
    """Create a new strategy."""
    try:
        return await create_strategy(
            name=request.name,
            strategy_type=request.type,
            config=request.config,
        )
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
        return await update_strategy(
            strategy_id=obj_id,
            name=request.name,
            config=request.config,
        )
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
