"""Strategy API endpoints."""

from fastapi import APIRouter, HTTPException
from trade_alpha.api.schemas import (
    StrategyCreateRequest,
    StrategyUpdateRequest,
    StrategyResponse,
)
from trade_alpha.strategy.service import (
    create_strategy,
    get_strategy_by_id,
    list_strategies,
    update_strategy,
    delete_strategy,
)

router = APIRouter(prefix="/strategies", tags=["strategies"])


def _doc_to_response(doc: dict) -> StrategyResponse:
    """Convert MongoDB document to response model."""
    return StrategyResponse(
        id=str(doc["_id"]),
        name=doc["name"],
        type=doc["type"],
        config=doc["config"],
        created_at=doc["created_at"],
    )


@router.get("", response_model=list[StrategyResponse])
def get_strategies():
    """Get all strategies."""
    strategies = list_strategies()
    return [_doc_to_response(s) for s in strategies]


@router.get("/{strategy_id}", response_model=StrategyResponse)
def get_strategy(strategy_id: str):
    """Get strategy by ID."""
    strategy = get_strategy_by_id(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return _doc_to_response(strategy)


@router.post("", response_model=StrategyResponse)
def create_strategy_endpoint(request: StrategyCreateRequest):
    """Create a new strategy."""
    strategy_id = create_strategy(
        name=request.name,
        strategy_type=request.type,
        config=request.config,
    )
    strategy = get_strategy_by_id(strategy_id)
    return _doc_to_response(strategy)


@router.put("/{strategy_id}")
def update_strategy_endpoint(strategy_id: str, request: StrategyUpdateRequest):
    """Update strategy."""
    success = update_strategy(
        strategy_id=strategy_id,
        name=request.name,
        config=request.config,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"message": "Strategy updated"}


@router.delete("/{strategy_id}")
def delete_strategy_endpoint(strategy_id: str):
    """Delete strategy."""
    success = delete_strategy(strategy_id)
    if not success:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"message": "Strategy deleted"}
