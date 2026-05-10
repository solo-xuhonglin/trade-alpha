"""Backtest API endpoints."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from trade_alpha.api.schemas import (
    BacktestRunRequest,
    BacktestResponse,
    TradeResponse,
    BacktestListResponse,
    TradeListResponse,
)
from trade_alpha.backtest.service import run_backtest as do_run_backtest
from trade_alpha.dao.mongodb import MongoDB

router = APIRouter(prefix="/backtests", tags=["backtests"])


class TradeFilterOptions(BaseModel):
    """Response model for trade filter options."""
    portfolios: List[dict] = []
    strategies: List[dict] = []
    trainings: List[dict] = []
    ts_codes: List[str] = []


def _backtest_to_response(doc: dict) -> BacktestResponse:
    """Convert backtest document to response model."""
    return BacktestResponse(
        id=str(doc["_id"]),
        portfolio_id=str(doc.get("portfolio_id")) if doc.get("portfolio_id") else None,
        strategy_id=str(doc.get("strategy_id")) if doc.get("strategy_id") else "",
        training_id=str(doc.get("training_id")) if doc.get("training_id") else "",
        ts_code=doc["ts_code"],
        start_date=doc["start_date"],
        end_date=doc["end_date"],
        initial_capital=doc["initial_capital"],
        final_value=doc["final_value"],
        total_return=doc["total_return"],
        annual_return=doc["annual_return"],
        benchmark_return=doc["benchmark_return"],
        max_drawdown=doc["max_drawdown"],
        sharpe_ratio=doc["sharpe_ratio"],
        win_rate=doc["win_rate"],
        total_trades=doc["total_trades"],
        total_fees=doc["total_fees"],
    )


@router.get("", response_model=BacktestListResponse)
def get_backtests(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """Get backtest history with pagination."""
    dao = MongoDB()
    coll = dao._get_collection("backtests")

    total = coll.count_documents({})
    skip = (page - 1) * page_size
    records = list(
        coll.find()
        .sort("_id", -1)
        .skip(skip)
        .limit(page_size)
    )
    dao.close()

    total_pages = (total + page_size - 1) // page_size
    return BacktestListResponse(
        items=[_backtest_to_response(r) for r in records],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/trades", response_model=TradeListResponse)
def get_all_trades(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    portfolio_id: Optional[str] = Query(None, description="Filter by portfolio ID"),
    strategy_id: Optional[str] = Query(None, description="Filter by strategy ID"),
    training_id: Optional[str] = Query(None, description="Filter by training ID"),
    ts_code: Optional[str] = Query(None, description="Filter by stock code"),
):
    """Get all trades with pagination and filtering."""
    from bson import ObjectId

    dao = MongoDB()
    coll_trades = dao._get_collection("backtest_trades")

    query_conditions = []

    if portfolio_id:
        try:
            query_conditions.append({"portfolio_id": ObjectId(portfolio_id)})
        except Exception:
            pass

    if strategy_id:
        try:
            query_conditions.append({"strategy_id": ObjectId(strategy_id)})
        except Exception:
            pass

    if training_id:
        try:
            query_conditions.append({"training_id": ObjectId(training_id)})
        except Exception:
            pass

    if ts_code:
        query_conditions.append({"ts_code": ts_code})

    final_query = {"$and": query_conditions} if query_conditions else {}

    total = coll_trades.count_documents(final_query)
    skip = (page - 1) * page_size
    records = list(
        coll_trades.find(final_query)
        .sort("trade_date", -1)
        .skip(skip)
        .limit(page_size)
    )
    dao.close()

    total_pages = (total + page_size - 1) // page_size
    return TradeListResponse(
        items=[
            TradeResponse(
                trade_date=r["trade_date"],
                action=r["action"],
                price=r["price"],
                shares=r["shares"],
                fee=r["fee"],
                cash_after=r["cash_after"],
                position_after=r["position_after"],
            )
            for r in records
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/trades/options", response_model=TradeFilterOptions)
def get_trade_filter_options():
    """Get filter options for trades page."""
    from bson import ObjectId

    dao = MongoDB()

    portfolios = list(dao._get_collection("portfolios").find({}, {"name": 1}))
    portfolio_list = [{"id": str(p["_id"]), "name": p.get("name", "未命名")} for p in portfolios]

    strategies = list(dao._get_collection("strategies").find({}, {"name": 1}))
    strategy_list = [{"id": str(s["_id"]), "name": s.get("name", "未命名")} for s in strategies]

    trainings = list(dao._get_collection("trainings").find({}, {"name": 1}))
    training_list = [{"id": str(t["_id"]), "name": t.get("name", "未命名")} for t in trainings]

    ts_codes = dao._get_collection("backtest_trades").distinct("ts_code")

    dao.close()

    return TradeFilterOptions(
        portfolios=portfolio_list,
        strategies=strategy_list,
        trainings=training_list,
        ts_codes=sorted(ts_codes)
    )


@router.get("/{backtest_id}", response_model=BacktestResponse)
def get_backtest(backtest_id: str):
    """Get backtest by ID."""
    from bson import ObjectId

    dao = MongoDB()
    doc = dao._get_collection("backtests").find_one({"_id": ObjectId(backtest_id)})
    dao.close()

    if not doc:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return _backtest_to_response(doc)


@router.get("/{backtest_id}/trades", response_model=TradeListResponse)
def get_backtest_trades(
    backtest_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """Get trades for a backtest with pagination."""
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        obj_id = ObjectId(backtest_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid backtest ID")

    dao = MongoDB()
    coll = dao._get_collection("backtest_trades")

    total = coll.count_documents({"backtest_id": obj_id})
    skip = (page - 1) * page_size
    records = list(
        coll.find({"backtest_id": obj_id})
        .sort("trade_date", 1)
        .skip(skip)
        .limit(page_size)
    )
    dao.close()

    total_pages = (total + page_size - 1) // page_size
    return TradeListResponse(
        items=[
            TradeResponse(
                trade_date=r["trade_date"],
                action=r["action"],
                price=r["price"],
                shares=r["shares"],
                fee=r["fee"],
                cash_after=r["cash_after"],
                position_after=r["position_after"],
            )
            for r in records
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("", response_model=BacktestResponse)
def run_backtest_endpoint(request: BacktestRunRequest):
    """Run backtest."""
    result = do_run_backtest(
        ts_code=request.ts_code,
        start_date=request.start_date,
        end_date=request.end_date,
        portfolio_id=request.portfolio_id,
        strategy_id=request.strategy_id,
        training_id=request.training_id,
    )

    from bson import ObjectId
    dao = MongoDB()
    doc = dao._get_collection("backtests").find_one({"_id": ObjectId(result.backtest_id)})
    dao.close()

    return _backtest_to_response(doc)


@router.delete("/{backtest_id}")
def delete_backtest(backtest_id: str):
    """Delete backtest and its trades."""
    from bson import ObjectId

    dao = MongoDB()
    dao._get_collection("backtest_trades").delete_many({"backtest_id": ObjectId(backtest_id)})
    result = dao._get_collection("backtests").delete_one({"_id": ObjectId(backtest_id)})
    dao.close()

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Backtest not found")

    return {"message": "Backtest deleted"}
