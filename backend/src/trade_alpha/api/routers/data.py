"""Data API endpoints."""

from typing import Optional
from fastapi import APIRouter, Query
from trade_alpha.api.schemas import DataFetchRequest, StockListResponse, StockDailyListResponse
from trade_alpha.data.service import (
    fetch_and_store,
    update_stock_list,
    list_stocks,
    list_stocks_by_mv_rank,
    find_stock_daily_by_ts_code,
    find_stock_daily_paginated,
    delete_stock_daily_by_ts_code,
)
from trade_alpha.indicators.service import calculate_all_indicators
from trade_alpha.scheduler.data_sync import update_single_stock_data_count
from trade_alpha.data.service import update_stock_data_count as bulk_update_data_count
from trade_alpha.utils.date_utils import to_db_format, to_api_format
from trade_alpha.api.validators import TradeDateQuery

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/stocks", response_model=StockListResponse)
async def list_stocks_endpoint(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=5000, description="Items per page"),
    start_rank: Optional[int] = Query(None, ge=1, description="Start market value rank (1-based)"),
    end_rank: Optional[int] = Query(None, ge=1, description="End market value rank (1-based)"),
):
    """List stocks with download status and pagination. If start_rank/end_rank provided, returns stocks in that rank range."""
    if start_rank is not None and end_rank is not None:
        # Return all stocks in rank range without pagination
        stocks = await list_stocks_by_mv_rank(start_rank, end_rank)
        total = len(stocks)
        page = 1
        page_size = total
        total_pages = 1
    else:
        # Regular pagination
        stocks, total = await list_stocks(page=page, page_size=page_size)
        total_pages = (total + page_size - 1) // page_size

    items = []
    for stock in stocks:
        items.append({
            "ts_code": stock.ts_code,
            "name": stock.name,
            "industry": stock.industry,
            "list_date": to_api_format(stock.list_date) if stock.list_date else None,
            "market": stock.market,
            "total_mv": stock.total_mv,
            "pe": stock.pe,
            "pb": stock.pb,
            "updated_at": stock.updated_at,
            "sync_status": stock.sync_status or "pending",
            "data_count": stock.data_count,
            "latest_date": to_api_format(stock.latest_date) if stock.latest_date else None,
        })

    return StockListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/stocks/update")
async def update_stocks_endpoint():
    """Update stock list from Tushare."""
    count = await update_stock_list()
    return {"updated_count": count}


@router.get("/{ts_code}")
async def get_data(
    ts_code: str,
    start_date: TradeDateQuery = None,
    end_date: TradeDateQuery = None,
):
    """Get stock daily data by date range. Returns all records sorted by trade_date ascending."""
    records = await find_stock_daily_by_ts_code(
        ts_code, 
        to_db_format(start_date) if start_date else None, 
        to_db_format(end_date) if end_date else None
    )
    # trade_date 保持数据库格式 YYYYMMDD，不转换
    return records


@router.get("/{ts_code}/paginated", response_model=StockDailyListResponse)
async def get_data_paginated(
    ts_code: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(500, ge=1, le=2000, description="Items per page"),
):
    """Get stock daily data with pagination, sorted by trade_date descending (newest first)."""
    records, total = await find_stock_daily_paginated(ts_code, page, page_size)
    total_pages = max(1, (total + page_size - 1) // page_size)

    items = []
    for r in records:
        items.append({
            "ts_code": r.ts_code,
            "trade_date": r.trade_date,
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "vol": r.vol,
            "amount": r.amount,
            "ma_5": r.ma_5,
            "ma_10": r.ma_10,
            "ma_20": r.ma_20,
            "ma_40": r.ma_40,
            "ma_60": r.ma_60,
            "macd": r.macd,
            "macd_signal": r.macd_signal,
            "macd_hist": r.macd_hist,
        })

    return StockDailyListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("")
async def fetch_data_endpoint(request: DataFetchRequest):
    """Fetch and store stock data, then calculate all indicators."""
    count = await fetch_and_store(
        ts_code=request.ts_code,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    if count > 0:
        await calculate_all_indicators(ts_code=request.ts_code)
        await update_single_stock_data_count(ts_code=request.ts_code)
    return {"ts_code": request.ts_code, "stored_count": count}


@router.delete("/{ts_code}")
async def delete_data_endpoint(ts_code: str):
    """Delete stock data."""
    count = await delete_stock_daily_by_ts_code(ts_code)
    return {"deleted_count": count}
