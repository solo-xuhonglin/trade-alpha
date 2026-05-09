"""Data API endpoints."""

from typing import Optional
from fastapi import APIRouter, Query
from trade_alpha.api.schemas import DataFetchRequest, DataRecordResponse
from trade_alpha.data.service import fetch_and_store
from trade_alpha.dao.mongodb import MongoDB

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/{ts_code}", response_model=list[DataRecordResponse])
def get_data(
    ts_code: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Get stock data."""
    dao = MongoDB()
    records = dao.find_by_ts_code(ts_code)

    if start_date:
        records = [r for r in records if r["trade_date"] >= start_date]
    if end_date:
        records = [r for r in records if r["trade_date"] <= end_date]

    dao.close()

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
    dao = MongoDB()
    result = dao._get_collection("daily").delete_many({"ts_code": ts_code})
    dao.close()
    return {"deleted_count": result.deleted_count}
