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
    exclude = {"id", "account_config_id", "training_id"}
    d = s.model_dump(exclude=exclude)
    d["id"] = str(s.id)
    return d


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
        data = request.model_dump(exclude_none=True, exclude={"type"})
        s = await create_strategy(strategy_type=request.type, **data)
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
        data = request.model_dump(exclude_none=True)
        s = await update_strategy(strategy_id=obj_id, **data)
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
