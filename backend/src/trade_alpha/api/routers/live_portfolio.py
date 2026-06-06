"""Live portfolio API router for manual position management."""

from datetime import datetime
from typing import Optional, List
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from trade_alpha.dao.live_portfolio import LivePortfolio, LivePositionEmbed
from trade_alpha.dao.stock_list import StockList

router = APIRouter(prefix="/live-portfolio", tags=["live-portfolio"])


# ---------------------------------------------------------------------------
# Request/Response schemas
# ---------------------------------------------------------------------------

class InitRequest(BaseModel):
    initial_cash: float


class CashRequest(BaseModel):
    total_cash: float


class SettingsRequest(BaseModel):
    buy_fee_rate: Optional[float] = None
    sell_fee_rate: Optional[float] = None
    stamp_tax_rate: Optional[float] = None
    min_fee: Optional[float] = None


class AddPositionRequest(BaseModel):
    ts_code: str
    stock_name: str
    shares: int
    price: float


class UpdatePositionRequest(BaseModel):
    shares: Optional[int] = None
    cost_price: Optional[float] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_or_create_portfolio() -> LivePortfolio:
    """Get the single portfolio document, creating with defaults if missing."""
    portfolio = await LivePortfolio.find_one()
    if portfolio is None:
        now = datetime.now()
        portfolio = LivePortfolio(
            total_cash=0.0,
            buy_fee_rate=0.0003,
            sell_fee_rate=0.0003,
            stamp_tax_rate=0.001,
            min_fee=5.0,
            positions=[],
            created_at=now,
            updated_at=now,
        )
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
    """Get portfolio with cash, positions and fee settings."""
    portfolio = await _get_or_create_portfolio()
    return _portfolio_to_dict(portfolio)


@router.post("/init")
async def init_portfolio(body: InitRequest):
    """Initialize portfolio with initial cash (only if not exists)."""
    existing = await LivePortfolio.find_one()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Portfolio already exists")
    now = datetime.now()
    portfolio = LivePortfolio(
        total_cash=body.initial_cash,
        positions=[],
        created_at=now,
        updated_at=now,
    )
    await portfolio.insert()
    return _portfolio_to_dict(portfolio)


@router.put("/cash")
async def update_cash(body: CashRequest):
    """Update total cash."""
    if body.total_cash < 0:
        raise HTTPException(status_code=400, detail="Cash cannot be negative")
    portfolio = await _get_or_create_portfolio()
    portfolio.total_cash = body.total_cash
    await _save_portfolio(portfolio)
    return _portfolio_to_dict(portfolio)


@router.put("/settings")
async def update_settings(body: SettingsRequest):
    """Update fee settings."""
    portfolio = await _get_or_create_portfolio()
    if body.buy_fee_rate is not None:
        portfolio.buy_fee_rate = body.buy_fee_rate
    if body.sell_fee_rate is not None:
        portfolio.sell_fee_rate = body.sell_fee_rate
    if body.stamp_tax_rate is not None:
        portfolio.stamp_tax_rate = body.stamp_tax_rate
    if body.min_fee is not None:
        portfolio.min_fee = body.min_fee
    await _save_portfolio(portfolio)
    return _portfolio_to_dict(portfolio)


@router.post("/positions")
async def add_position(body: AddPositionRequest):
    """Add a position, auto-calculate weighted average cost and deduct cash.

    Deducts: shares * price + max(shares * price * buy_fee_rate, min_fee)
    """
    if body.shares <= 0 or body.price <= 0:
        raise HTTPException(status_code=400, detail="Shares and price must be positive")
    portfolio = await _get_or_create_portfolio()

    cost = body.shares * body.price
    fee = max(cost * portfolio.buy_fee_rate, portfolio.min_fee)
    total_deduct = cost + fee

    if portfolio.total_cash < total_deduct:
        raise HTTPException(status_code=400, detail=f"Insufficient cash: need {total_deduct:.2f}, have {portfolio.total_cash:.2f}")

    now = datetime.now()
    existing_idx = None
    for i, pos in enumerate(portfolio.positions):
        if pos.ts_code == body.ts_code:
            existing_idx = i
            break

    if existing_idx is not None:
        existing = portfolio.positions[existing_idx]
        new_shares = existing.shares + body.shares
        new_cost_price = (existing.total_cost + cost) / new_shares
        portfolio.positions[existing_idx] = LivePositionEmbed(
            id=existing.id,
            ts_code=existing.ts_code,
            stock_name=existing.stock_name,
            shares=new_shares,
            cost_price=round(new_cost_price, 4),
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

    portfolio.total_cash -= total_deduct
    await _save_portfolio(portfolio)
    return _portfolio_to_dict(portfolio)


@router.put("/positions/{position_id}")
async def update_position(position_id: str, body: UpdatePositionRequest):
    """Update position shares and/or cost price, adjust cash by cost delta."""
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
    delta = new_total_cost - old.total_cost

    if portfolio.total_cash < delta:
        raise HTTPException(status_code=400, detail=f"Insufficient cash for cost increase: need {delta:.2f}, have {portfolio.total_cash:.2f}")

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
    portfolio.total_cash -= delta
    await _save_portfolio(portfolio)
    return _portfolio_to_dict(portfolio)


@router.delete("/positions/{position_id}")
async def delete_position(position_id: str):
    """Delete a position and add its total_cost back to cash."""
    portfolio = await _get_or_create_portfolio()

    target_idx = None
    for i, pos in enumerate(portfolio.positions):
        if pos.id == position_id:
            target_idx = i
            break

    if target_idx is None:
        raise HTTPException(status_code=404, detail="Position not found")

    removed = portfolio.positions.pop(target_idx)
    portfolio.total_cash += removed.total_cost
    await _save_portfolio(portfolio)
    return _portfolio_to_dict(portfolio)


@router.get("/stocks/search")
async def search_stocks(q: str = ""):
    """Search stocks from StockList by ts_code or name (fuzzy match)."""
    if not q.strip():
        return {"items": []}
    keyword = q.strip()
    items = await StockList.find(
        {"$or": [
            {"ts_code": {"$regex": keyword, "$options": "i"}},
            {"name": {"$regex": keyword, "$options": "i"}},
        ]}
    ).limit(20).to_list()
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
        "total_cash": p.total_cash,
        "buy_fee_rate": p.buy_fee_rate,
        "sell_fee_rate": p.sell_fee_rate,
        "stamp_tax_rate": p.stamp_tax_rate,
        "min_fee": p.min_fee,
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