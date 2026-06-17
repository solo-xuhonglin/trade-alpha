"""Trade calendar API endpoints."""

from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from trade_alpha.data.service import fetch_and_store_trade_calendar, get_trade_calendar_records
from trade_alpha.scheduler.daily_update_job import run_daily_update_job

router = APIRouter(prefix="/trade-calendar", tags=["trade-calendar"])


@router.post("/sync")
async def sync_trade_calendar_endpoint():
    """Fetch and store trading calendar from Tushare."""
    try:
        result = await fetch_and_store_trade_calendar()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/daily-update")
async def trigger_daily_update():
    """Manually trigger the daily stock data update."""
    try:
        await run_daily_update_job()
        return {"message": "Daily update completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def get_trade_calendar_endpoint(
    start_date: Optional[str] = Query(None, description="Start date (YYYYMMDD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYYMMDD)"),
):
    """Get trade calendar records."""
    records = await get_trade_calendar_records(start_date, end_date)
    return records