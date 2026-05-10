"""Portfolio API endpoints."""

from fastapi import APIRouter, HTTPException
from trade_alpha.api.schemas import (
    PortfolioCreateRequest,
    PortfolioUpdateRequest,
    PortfolioResponse,
)
from trade_alpha.portfolio.service import (
    create_portfolio,
    get_portfolio_by_id,
    get_portfolio,
    list_portfolios,
)

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


def _doc_to_response(doc: dict) -> PortfolioResponse:
    """Convert MongoDB document to response model."""
    return PortfolioResponse(
        id=str(doc["_id"]),
        name=doc["name"],
        initial_capital=doc["initial_capital"],
        cash=doc.get("cash", doc["initial_capital"]),
        position=doc.get("position", 0),
        buy_fee_rate=doc["buy_fee_rate"],
        sell_fee_rate=doc["sell_fee_rate"],
        stamp_tax_rate=doc["stamp_tax_rate"],
        min_fee=doc["min_fee"],
    )


@router.get("", response_model=list[PortfolioResponse])
def get_portfolios():
    """Get all portfolios."""
    portfolios = list_portfolios()
    return [_doc_to_response(p) for p in portfolios]


@router.get("/{portfolio_id}", response_model=PortfolioResponse)
def get_portfolio_endpoint(portfolio_id: str):
    """Get portfolio by ID."""
    portfolio = get_portfolio_by_id(portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return _doc_to_response(portfolio)


@router.post("", response_model=PortfolioResponse)
def create_portfolio_endpoint(request: PortfolioCreateRequest):
    """Create a new portfolio."""
    existing = get_portfolio_by_name(request.name)
    if existing:
        raise HTTPException(status_code=400, detail="Portfolio name already exists")

    portfolio_id = create_portfolio(
        name=request.name,
        initial_capital=request.initial_capital,
        buy_fee_rate=request.buy_fee_rate,
        sell_fee_rate=request.sell_fee_rate,
        stamp_tax_rate=request.stamp_tax_rate,
        min_fee=request.min_fee,
    )
    portfolio = get_portfolio_by_id(portfolio_id)
    return _doc_to_response(portfolio)


@router.put("/{portfolio_id}")
def update_portfolio_endpoint(portfolio_id: str, request: PortfolioUpdateRequest):
    """Update portfolio."""
    from trade_alpha.portfolio.service import update_portfolio

    success = update_portfolio(
        portfolio_id=portfolio_id,
        buy_fee_rate=request.buy_fee_rate,
        sell_fee_rate=request.sell_fee_rate,
        stamp_tax_rate=request.stamp_tax_rate,
        min_fee=request.min_fee,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return {"message": "Portfolio updated"}


@router.delete("/{portfolio_id}")
def delete_portfolio_endpoint(portfolio_id: str):
    """Delete portfolio."""
    from trade_alpha.portfolio.service import delete_portfolio

    success = delete_portfolio(portfolio_id)
    if not success:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return {"message": "Portfolio deleted"}
