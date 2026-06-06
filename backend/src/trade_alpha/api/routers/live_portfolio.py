"""Live portfolio API router for manual position management."""

from datetime import datetime
from typing import List
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from trade_alpha.dao.live_portfolio import LivePortfolio, LivePositionEmbed
from trade_alpha.dao.stock_list import StockList

router = APIRouter(prefix="/live-portfolio", tags=["live-portfolio"])


# ---------------------------------------------------------------------------
# Request/Response schemas
# ---------------------------------------------------------------------------

class AddPositionRequest(BaseModel):
    ts_code: str
    stock_name: str
    shares: int
    price: float


class UpdatePositionRequest(BaseModel):
    shares: int | None = None
    cost_price: float | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_or_create_portfolio() -> LivePortfolio:
    """Get the single portfolio document, creating with defaults if missing."""
    portfolio = await LivePortfolio.find_one()
    if portfolio is None:
        now = datetime.now()
        portfolio = LivePortfolio(positions=[], created_at=now, updated_at=now)
        await portfolio.insert()
    return portfolio


async def _save_portfolio(p: LivePortfolio) -> None:
    p.updated_at = datetime.now()
    await p.save()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/")
async def get_portfolio():
    """Get portfolio with positions."""
    portfolio = await _get_or_create_portfolio()
    return _portfolio_to_dict(portfolio)


@router.post("/positions")
async def add_position(body: AddPositionRequest):
    """Add a position (no cash deduction)."""
    if body.shares <= 0 or body.price <= 0:
        raise HTTPException(status_code=400, detail="Shares and price must be positive")
    portfolio = await _get_or_create_portfolio()

    now = datetime.now()
    cost = body.shares * body.price

    existing_idx = None
    for i, pos in enumerate(portfolio.positions):
        if pos.ts_code == body.ts_code:
            existing_idx = i
            break

    if existing_idx is not None:
        existing = portfolio.positions[existing_idx]
        new_shares = existing.shares + body.shares
        new_cost_price = round((existing.total_cost + cost) / new_shares, 4)
        portfolio.positions[existing_idx] = LivePositionEmbed(
            id=existing.id,
            ts_code=existing.ts_code,
            stock_name=existing.stock_name,
            shares=new_shares,
            cost_price=new_cost_price,
            total_cost=round(new_shares * new_cost_price, 2),
            created_at=existing.created_at,
            updated_at=now,
        )
    else:
        portfolio.positions.append(LivePositionEmbed(
            id=str(uuid4()),
            ts_code=body.ts_code,
            stock_name=body.stock_name,
            shares=body.shares,
            cost_price=body.price,
            total_cost=round(cost, 2),
            created_at=now,
            updated_at=now,
        ))

    await _save_portfolio(portfolio)
    return _portfolio_to_dict(portfolio)


@router.put("/positions/{position_id}")
async def update_position(position_id: str, body: UpdatePositionRequest):
    """Update position shares and/or cost price (no cash adjustment)."""
    if body.shares is not None and body.shares <= 0:
        raise HTTPException(status_code=400, detail="Shares must be positive")
    if body.cost_price is not None and body.cost_price <= 0:
        raise HTTPException(status_code=400, detail="Cost price must be positive")

    portfolio = await _get_or_create_portfolio()

    target_idx = None
    for i, pos in enumerate(portfolio.positions):
        if pos.id == position_id:
            target_idx = i
            break

    if target_idx is None:
        raise HTTPException(status_code=404, detail="Position not found")

    old = portfolio.positions[target_idx]
    new_shares = body.shares if body.shares is not None else old.shares
    new_cost_price = body.cost_price if body.cost_price is not None else old.cost_price
    new_total_cost = round(new_shares * new_cost_price, 2)

    now = datetime.now()
    portfolio.positions[target_idx] = LivePositionEmbed(
        id=old.id,
        ts_code=old.ts_code,
        stock_name=old.stock_name,
        shares=new_shares,
        cost_price=new_cost_price,
        total_cost=new_total_cost,
        created_at=old.created_at,
        updated_at=now,
    )
    await _save_portfolio(portfolio)
    return _portfolio_to_dict(portfolio)


@router.delete("/positions/{position_id}")
async def delete_position(position_id: str):
    """Delete a position (no cash adjustment)."""
    portfolio = await _get_or_create_portfolio()

    target_idx = None
    for i, pos in enumerate(portfolio.positions):
        if pos.id == position_id:
            target_idx = i
            break

    if target_idx is None:
        raise HTTPException(status_code=404, detail="Position not found")

    portfolio.positions.pop(target_idx)
    await _save_portfolio(portfolio)
    return _portfolio_to_dict(portfolio)


@router.get("/stocks/search")
async def search_stocks(q: str = ""):
    """Search stocks from StockList by ts_code or name (fuzzy match).

    When q is empty, returns top 100 stocks by market cap.
    """
    keyword = q.strip()
    if keyword:
        items = await StockList.find(
            {"$or": [
                {"ts_code": {"$regex": keyword, "$options": "i"}},
                {"name": {"$regex": keyword, "$options": "i"}},
            ]}
        ).sort(-StockList.total_mv).limit(20).to_list()
    else:
        items = await StockList.find(
            StockList.total_mv != None
        ).sort(-StockList.total_mv).limit(100).to_list()
    return {
        "items": [
            {"ts_code": s.ts_code, "name": s.name, "industry": s.industry, "market": s.market}
            for s in items
        ]
    }


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _portfolio_to_dict(p: LivePortfolio) -> dict:
    return {
        "id": str(p.id),
        "positions": [
            {
                "id": pos.id,
                "ts_code": pos.ts_code,
                "stock_name": pos.stock_name,
                "shares": pos.shares,
                "cost_price": pos.cost_price,
                "total_cost": pos.total_cost,
                "created_at": pos.created_at.isoformat(),
                "updated_at": pos.updated_at.isoformat(),
            }
            for pos in p.positions
        ],
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }