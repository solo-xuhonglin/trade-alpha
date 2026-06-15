"""Backtest records API router - thin pass-through to backtest_service."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from beanie import PydanticObjectId

from trade_alpha.execution.backtest_service import (
    list_backtest_results,
    delete_backtest_result,
    get_backtest_trades,
    get_trades_by_ts_code,
    get_pnl_details,
    get_prediction_stocks,
    get_stock_predictions,
    get_excluded_stocks,
    get_forced_sell_stocks,
    list_all_trades,
    get_daily_snapshots,
    get_daily_details,
    get_trade_filter_options,
)

router = APIRouter(prefix="/backtests", tags=["backtest-records"])


def _parse_id(result_id: str) -> PydanticObjectId:
    """Parse and validate a result ID string."""
    try:
        return PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")


@router.get("")
async def list_results(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all backtest results with pagination."""
    return await list_backtest_results(page=page, page_size=page_size)


@router.delete("/{result_id}")
async def delete_result(result_id: str):
    """Delete a backtest result and its related trades."""
    obj_id = _parse_id(result_id)
    deleted = await delete_backtest_result(obj_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Result not found")
    return {"message": "Backtest result deleted"}


@router.get("/{result_id}/trades")
async def list_trades(
    result_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Get trades for a specific backtest result."""
    obj_id = _parse_id(result_id)
    return await get_backtest_trades(result_id=obj_id, page=page, page_size=page_size)


@router.get("/{result_id}/trades/{ts_code}")
async def trades_by_ts_code(result_id: str, ts_code: str):
    """Get trades for a specific stock in a backtest result."""
    obj_id = _parse_id(result_id)
    return await get_trades_by_ts_code(result_id=obj_id, ts_code=ts_code)


@router.get("/{result_id}/pnl-details")
async def pnl_details(result_id: str):
    """Get PnL details grouped by stock for a backtest result."""
    obj_id = _parse_id(result_id)
    return await get_pnl_details(result_id=obj_id)


@router.get("/{result_id}/prediction-stocks")
async def prediction_stocks(result_id: str):
    """Get all stocks with predictions for a backtest result."""
    obj_id = _parse_id(result_id)
    return await get_prediction_stocks(result_id=obj_id)


@router.get("/{result_id}/predictions/{ts_code}")
async def stock_predictions(result_id: str, ts_code: str):
    """Get daily predictions for a specific stock in a backtest result."""
    obj_id = _parse_id(result_id)
    return await get_stock_predictions(result_id=obj_id, ts_code=ts_code)


@router.get("/{result_id}/excluded-stocks")
async def excluded_stocks(result_id: str):
    """Get explosion filter statistics for a backtest result."""
    obj_id = _parse_id(result_id)
    return await get_excluded_stocks(result_id=obj_id)


@router.get("/{result_id}/forced-sell-stocks")
async def forced_sell_stocks(result_id: str):
    """Get forced sell records for a backtest result."""
    obj_id = _parse_id(result_id)
    return await get_forced_sell_stocks(result_id=obj_id)


@router.get("/trades")
async def all_trades(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    account_config_id: Optional[str] = None,
    backtest_id: Optional[str] = None,
    training_id: Optional[str] = None,
    ts_code: Optional[str] = None,
):
    """List all trades with optional filters."""
    return await list_all_trades(
        page=page,
        page_size=page_size,
        account_config_id=account_config_id,
        backtest_id=backtest_id,
        training_id=training_id,
        ts_code=ts_code,
    )


@router.get("/{result_id}/daily-snapshots")
async def daily_snapshots(result_id: str):
    """Get daily snapshots for a backtest result (equity curve)."""
    obj_id = _parse_id(result_id)
    return await get_daily_snapshots(result_id=obj_id)


@router.get("/{result_id}/daily-details")
async def daily_details(result_id: str):
    """Get daily detailed snapshots with positions and trades."""
    obj_id = _parse_id(result_id)
    return await get_daily_details(result_id=obj_id)


@router.get("/trades/options")
async def trade_filter_options():
    """Get filter options for trade list."""
    return await get_trade_filter_options()