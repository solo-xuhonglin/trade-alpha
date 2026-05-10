"""Data API endpoints."""

from typing import Optional
from fastapi import APIRouter, Query
from trade_alpha.api.schemas import DataFetchRequest, DataRecordResponse, StockResponse, StockListUpdateResponse, StockListResponse
from trade_alpha.data.service import fetch_and_store, update_stock_list
from trade_alpha.dao import DailyDAO, StockListDAO

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/stocks", response_model=StockListResponse)
def list_stocks(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """List stocks with download status and pagination."""
    stock_dao = StockListDAO()
    daily_dao = DailyDAO()

    total = stock_dao.count_stocks()
    skip = (page - 1) * page_size
    stocks = stock_dao.list_stocks(skip=skip, limit=page_size)
    downloaded_summary = daily_dao.get_downloaded_summary()

    downloaded_map = {
        item["ts_code"]: {
            "count": item["count"],
            "latest_date": item["latest_date"]
        }
        for item in downloaded_summary
    }

    items = []
    for stock in stocks:
        ts_code = stock["ts_code"]
        downloaded = downloaded_map.get(ts_code)
        items.append(StockResponse(
            ts_code=stock["ts_code"],
            name=stock["name"],
            industry=stock.get("industry"),
            list_date=stock.get("list_date"),
            market=stock.get("market"),
            total_mv=stock.get("total_mv"),
            pe=stock.get("pe"),
            pb=stock.get("pb"),
            updated_at=stock.get("updated_at"),
            is_downloaded=downloaded is not None,
            data_count=downloaded["count"] if downloaded else None,
            latest_date=downloaded["latest_date"] if downloaded else None,
        ))

    total_pages = (total + page_size - 1) // page_size
    return StockListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/stocks/update", response_model=StockListUpdateResponse)
def update_stocks():
    """Update stock list from Tushare."""
    count = update_stock_list()
    return StockListUpdateResponse(updated_count=count)


@router.get("/{ts_code}", response_model=list[DataRecordResponse])
def get_data(
    ts_code: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Get stock data."""
    dao = DailyDAO()
    records = dao.find_by_ts_code(ts_code)

    if start_date:
        records = [r for r in records if r["trade_date"] >= start_date]
    if end_date:
        records = [r for r in records if r["trade_date"] <= end_date]

    return [
        DataRecordResponse(
            ts_code=r["ts_code"],
            trade_date=r["trade_date"],
            open=r["open"],
            high=r["high"],
            low=r["low"],
            close=r["close"],
            vol=r["vol"],
            amount=r["amount"],
            ma_5=r.get("ma_5"),
            ma_10=r.get("ma_10"),
            ma_20=r.get("ma_20"),
            ma_60=r.get("ma_60"),
            macd=r.get("macd"),
            macd_signal=r.get("macd_signal"),
            macd_hist=r.get("macd_hist"),
        )
        for r in records
    ]


@router.post("")
def fetch_data(request: DataFetchRequest):
    """Fetch and store stock data."""
    count = fetch_and_store(
        ts_code=request.ts_code,
        start_date=request.start_date,
        end_date=request.end_date,
    )
    return {"ts_code": request.ts_code, "stored_count": count}


@router.delete("/{ts_code}")
def delete_data(ts_code: str):
    """Delete stock data."""
    dao = DailyDAO()
    count = dao.delete_by_ts_code(ts_code)
    return {"deleted_count": count}
