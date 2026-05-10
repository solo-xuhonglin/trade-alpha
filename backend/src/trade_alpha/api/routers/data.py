"""Data API endpoints."""

from typing import Optional
from fastapi import APIRouter, Query
from trade_alpha.api.schemas import DataFetchRequest, StockListResponse
from trade_alpha.data.service import (
    fetch_and_store,
    update_stock_list,
    list_stocks,
    get_downloaded_summary,
    find_stock_daily_by_ts_code,
    delete_stock_daily_by_ts_code,
)

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/stocks", response_model=StockListResponse)
async def list_stocks_endpoint(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """List stocks with download status and pagination."""
    stocks, total = await list_stocks(page=page, page_size=page_size)
    downloaded_summary = await get_downloaded_summary()

    downloaded_map = {
        item["ts_code"]: {
            "count": item["count"],
            "latest_date": item["latest_date"]
        }
        for item in downloaded_summary
    }

    items = []
    for stock in stocks:
        ts_code = stock.ts_code
        downloaded = downloaded_map.get(ts_code)
        items.append({
            "ts_code": stock.ts_code,
            "name": stock.name,
            "industry": stock.industry,
            "list_date": stock.list_date,
            "market": stock.market,
            "total_mv": stock.total_mv,
            "pe": stock.pe,
            "pb": stock.pb,
            "updated_at": stock.updated_at,
            "is_downloaded": downloaded is not None,
            "data_count": downloaded["count"] if downloaded else None,
            "latest_date": downloaded["latest_date"] if downloaded else None,
        })

    total_pages = (total + page_size - 1) // page_size
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
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Get stock data."""
    records = await find_stock_daily_by_ts_code(ts_code, start_date, end_date)
    return records


@router.post("")
async def fetch_data_endpoint(request: DataFetchRequest):
    """Fetch and store stock data."""
    count = await fetch_and_store(
        ts_code=request.ts_code,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    return {"ts_code": request.ts_code, "stored_count": count}


@router.delete("/{ts_code}")
async def delete_data_endpoint(ts_code: str):
    """Delete stock data."""
    count = await delete_stock_daily_by_ts_code(ts_code)
    return {"deleted_count": count}
