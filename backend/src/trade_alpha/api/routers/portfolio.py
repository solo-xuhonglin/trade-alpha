"""Portfolio API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from beanie import PydanticObjectId

from trade_alpha.portfolio import (
    create_portfolio,
    get_portfolio_by_id,
    list_portfolios,
    update_portfolio,
    delete_portfolio,
)

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


class PortfolioCreateRequest(BaseModel):
    name: str
    initial_capital: float = 100000.0
    buy_fee_rate: float = 0.0003
    sell_fee_rate: float = 0.0003
    stamp_tax_rate: float = 0.001
    min_fee: float = 5.0


class PortfolioUpdateRequest(BaseModel):
    buy_fee_rate: float | None = None
    sell_fee_rate: float | None = None
    stamp_tax_rate: float | None = None
    min_fee: float | None = None


@router.get("")
async def get_portfolios():
    """List all portfolios."""
    return await list_portfolios()


@router.get("/{portfolio_id}")
async def get_portfolio(portfolio_id: PydanticObjectId):
    """Get portfolio by ID."""
    portfolio = await get_portfolio_by_id(portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


@router.post("")
async def create_portfolio_endpoint(request: PortfolioCreateRequest):
    """Create a new portfolio."""
    try:
        portfolio = await create_portfolio(
            name=request.name,
            initial_capital=request.initial_capital,
            buy_fee_rate=request.buy_fee_rate,
            sell_fee_rate=request.sell_fee_rate,
            stamp_tax_rate=request.stamp_tax_rate,
            min_fee=request.min_fee,
        )
        return portfolio
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{portfolio_id}")
async def update_portfolio_endpoint(portfolio_id: PydanticObjectId, request: PortfolioUpdateRequest):
    """Update portfolio."""
    update_data = {k: v for k, v in request.model_dump().items() if v is not None}
    portfolio = await update_portfolio(portfolio_id, **update_data)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


@router.delete("/{portfolio_id}")
async def delete_portfolio_endpoint(portfolio_id: PydanticObjectId):
    """Delete portfolio."""
    deleted = await delete_portfolio(portfolio_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return {"message": "Portfolio deleted"}
