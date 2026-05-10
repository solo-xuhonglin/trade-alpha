"""Backtest API endpoints."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from beanie import PydanticObjectId
from trade_alpha.api.schemas import BacktestRunRequest
from trade_alpha.backtest.service import (
    run_backtest as do_run_backtest,
    list_backtests,
    get_backtest_by_id,
    delete_backtest,
    list_trades,
    list_trades_by_backtest_id,
    list_portfolios_for_filter,
    list_strategies_for_filter,
    list_trainings_for_filter,
    get_distinct_ts_codes,
)
from trade_alpha.dao import BacktestTrade

router = APIRouter(prefix="/backtests", tags=["backtests"])


class TradeFilterOptions(BaseModel):
    portfolios: list = []
    strategies: list = []
    trainings: list = []
    ts_codes: list[str] = []


class BacktestListResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int


class TradeListResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int


@router.get("", response_model=BacktestListResponse)
async def get_backtests(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """Get backtest history with pagination."""
    results, total = await list_backtests(page=page, page_size=page_size)
    
    total_pages = (total + page_size - 1) // page_size
    return BacktestListResponse(
        items=results,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/trades/options", response_model=TradeFilterOptions)
async def get_trade_filter_options():
    """Get filter options for trades page."""
    portfolios = await list_portfolios_for_filter()
    strategies = await list_strategies_for_filter()
    trainings = await list_trainings_for_filter()
    ts_codes = await get_distinct_ts_codes()
    
    return TradeFilterOptions(
        portfolios=portfolios,
        strategies=strategies,
        trainings=trainings,
        ts_codes=ts_codes
    )


@router.get("/trades", response_model=TradeListResponse)
async def get_all_trades(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    portfolio_id: Optional[str] = Query(None, description="Filter by portfolio ID"),
    strategy_id: Optional[str] = Query(None, description="Filter by strategy ID"),
    training_id: Optional[str] = Query(None, description="Filter by training ID"),
    ts_code: Optional[str] = Query(None, description="Filter by stock code"),
):
    """Get all trades with pagination and filtering."""
    p_id = PydanticObjectId(portfolio_id) if portfolio_id else None
    s_id = PydanticObjectId(strategy_id) if strategy_id else None
    t_id = PydanticObjectId(training_id) if training_id else None
    
    results, total = await list_trades(
        page=page,
        page_size=page_size,
        portfolio_id=p_id,
        strategy_id=s_id,
        training_id=t_id,
        ts_code=ts_code,
    )
    
    total_pages = (total + page_size - 1) // page_size
    return TradeListResponse(
        items=results,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{backtest_id}")
async def get_backtest(backtest_id: str):
    """Get backtest by ID."""
    try:
        obj_id = PydanticObjectId(backtest_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid backtest ID")
    
    backtest = await get_backtest_by_id(obj_id)
    if not backtest:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return backtest


@router.get("/{backtest_id}/trades", response_model=TradeListResponse)
async def get_backtest_trades(
    backtest_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """Get trades for a backtest with pagination."""
    try:
        obj_id = PydanticObjectId(backtest_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid backtest ID")
    
    results, total = await list_trades_by_backtest_id(obj_id, page=page, page_size=page_size)
    
    total_pages = (total + page_size - 1) // page_size
    return TradeListResponse(
        items=results,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("")
async def run_backtest_endpoint(request: BacktestRunRequest):
    """Run backtest."""
    try:
        p_id = PydanticObjectId(request.portfolio_id)
        s_id = PydanticObjectId(request.strategy_id)
        t_id = PydanticObjectId(request.training_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    result = await do_run_backtest(
        ts_code=request.ts_code,
        start_date=request.start_date,
        end_date=request.end_date,
        portfolio_id=p_id,
        strategy_id=s_id,
        training_id=t_id,
    )
    
    from trade_alpha.backtest.service import get_backtest_by_id
    backtest = await get_backtest_by_id(PydanticObjectId(result.backtest_id))
    return backtest


@router.delete("/{backtest_id}")
async def delete_backtest_endpoint(backtest_id: str):
    """Delete backtest and its trades."""
    try:
        obj_id = PydanticObjectId(backtest_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid backtest ID")
    
    deleted = await delete_backtest(obj_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return {"message": "Backtest deleted"}
