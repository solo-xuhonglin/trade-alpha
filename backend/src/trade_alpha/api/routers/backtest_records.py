"""Backtest records API router."""

from fastapi import APIRouter, HTTPException, Query
from beanie import PydanticObjectId
from typing import Optional, List

from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.execution import ExecutionResult
from trade_alpha.dao.execution_daily_snapshot import ExecutionDailySnapshot
from trade_alpha.dao.execution_trade import ExecutionTrade
from trade_alpha.dao.stock_list import StockList

router = APIRouter(prefix="/backtests", tags=["backtest-records"])


@router.get("")
async def list_backtest_results(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all backtest results with pagination."""
    total = await ExecutionResult.find_all().count()
    results = await ExecutionResult.find_all().sort(-ExecutionResult.created_at).skip((page - 1) * page_size).limit(page_size).to_list()

    items = []
    for result in results:
        account_config = await AccountConfig.get(result.account_config_id) if result.account_config_id else None

        items.append({
            "id": str(result.id),
            "name": result.name,
            "strategy_id": None,
            "training_id": str(result.training_id) if result.training_id else None,
            "ts_code": result.ts_code,
            "start_date": result.start_date,
            "end_date": result.end_date,
            "initial_capital": result.initial_capital,
            "final_value": result.final_value,
            "total_return": result.total_return,
            "annual_return": getattr(result, "annual_return", None),
            "benchmark_return": getattr(result, "benchmark_return", None),
            "max_drawdown": result.max_drawdown,
            "sharpe_ratio": result.sharpe_ratio,
            "win_rate": result.win_rate,
            "total_trades": result.total_trades,
            "total_fees": result.total_fees,
            "volatility": result.volatility,
            "baseline_return": result.baseline_return,
            "excess_return": result.excess_return,
            "baseline_max_drawdown": result.baseline_max_drawdown,
            "avg_hold_days": result.avg_hold_days,
            "account_config_name": account_config.name if account_config else None,
            "strategy_name": None,
            "created_at": result.created_at,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.delete("/{result_id}")
async def delete_backtest_result(result_id: str):
    """Delete a backtest result and its related trades."""
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    result = await ExecutionResult.get(obj_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    await ExecutionTrade.find(ExecutionTrade.backtest_id == obj_id).delete()
    await result.delete()

    return {"message": "Backtest result deleted"}


@router.get("/{result_id}/trades")
async def get_backtest_trades(
    result_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Get trades for a specific backtest result."""
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    result = await ExecutionResult.get(obj_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    query = ExecutionTrade.find(ExecutionTrade.backtest_id == obj_id)
    total = await query.count()
    trades = await query.sort(ExecutionTrade.trade_date).skip((page - 1) * page_size).limit(page_size).to_list()

    return {
        "items": [
            {
                "trade_date": trade.trade_date,
                "action": trade.action,
                "price": trade.price,
                "shares": trade.shares,
                "fee": trade.fee,
                "cash_after": trade.cash_after,
                "position_after": getattr(trade, "position_after", 0),
            }
            for trade in trades
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/{result_id}/prediction-stocks")
async def get_prediction_stocks(result_id: str):
    """Get stocks that have prediction data in a backtest result."""
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    result = await ExecutionResult.get(obj_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    snapshot = await ExecutionDailySnapshot.find_one(
        ExecutionDailySnapshot.backtest_id == obj_id,
        ExecutionDailySnapshot.predictions != {},
    )
    if not snapshot:
        return {"items": []}

    ts_codes = list(snapshot.predictions.keys())
    stocks = await StockList.find(StockList.ts_code.in_(ts_codes)).to_list()
    stock_map = {s.ts_code: s.name for s in stocks}

    items = [
        {"ts_code": ts_code, "stock_name": stock_map.get(ts_code, ts_code)}
        for ts_code in ts_codes
    ]

    return {"items": items}


@router.get("/{result_id}/predictions/{ts_code}")
async def get_stock_predictions(result_id: str, ts_code: str):
    """Get daily predictions for a specific stock in a backtest result."""
    try:
        obj_id = PydanticObjectId(result_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid result ID")

    result = await ExecutionResult.get(obj_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    snapshots = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == obj_id,
    ).sort(ExecutionDailySnapshot.date).to_list()

    stock = await StockList.find_one(StockList.ts_code == ts_code)
    stock_name = stock.name if stock else ts_code

    items = []
    for snap in snapshots:
        pred = snap.predictions.get(ts_code)
        if pred is not None:
            items.append({
                "trade_date": snap.date,
                "score": pred.get("score"),
                "up_prob_3d": pred.get("up_prob_3d"),
                "up_prob_5d": pred.get("up_prob_5d"),
            })

    return {
        "ts_code": ts_code,
        "stock_name": stock_name,
        "start_date": items[0]["trade_date"] if items else None,
        "end_date": items[-1]["trade_date"] if items else None,
        "items": items,
    }


@router.get("/trades")
async def list_all_trades(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    account_config_id: Optional[str] = None,
    strategy_id: Optional[str] = None,
    training_id: Optional[str] = None,
    ts_code: Optional[str] = None,
):
    """List all trades with optional filters."""
    query = ExecutionTrade.find_all()

    if account_config_id or strategy_id or training_id or ts_code:
        result_ids = []
        result_query = ExecutionResult.find_all()
        results = await result_query.to_list()

        for result in results:
            match = True
            if account_config_id and str(result.account_config_id) != account_config_id:
                match = False
            if training_id and str(result.training_id) != training_id:
                match = False
            if ts_code and result.ts_code != ts_code:
                match = False
            if match:
                result_ids.append(result.id)

        query = ExecutionTrade.find(ExecutionTrade.backtest_id.in_(result_ids)) if result_ids else ExecutionTrade.find(ExecutionTrade.backtest_id == PydanticObjectId("000000000000000000000000"))

    total = await query.count()
    trades = await query.sort(ExecutionTrade.trade_date).skip((page - 1) * page_size).limit(page_size).to_list()

    return {
        "items": [
            {
                "trade_date": trade.trade_date,
                "action": trade.action,
                "price": trade.price,
                "shares": trade.shares,
                "fee": trade.fee,
                "cash_after": trade.cash_after,
                "position_after": getattr(trade, "position_after", 0),
            }
            for trade in trades
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/trades/options")
async def get_trade_filter_options():
    """Get filter options for trade list."""
    account_configs = await AccountConfig.find_all().to_list()

    return {
        "account_configs": [
            {"id": str(config.id), "name": config.name}
            for config in account_configs
        ],
        "strategies": [],
        "trainings": [],
        "ts_codes": [],
    }
