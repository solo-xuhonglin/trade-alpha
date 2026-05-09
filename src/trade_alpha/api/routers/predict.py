"""Predict API endpoints."""

from fastapi import APIRouter, HTTPException
from trade_alpha.api.schemas import PredictRequest, PredictResponse
from trade_alpha.predict.service import predict as do_predict
from trade_alpha.dao.mongodb import MongoDB

router = APIRouter(prefix="/predict", tags=["predict"])


@router.get("/{ts_code}", response_model=PredictResponse)
def get_prediction(ts_code: str):
    """Get latest prediction for a stock."""
    dao = MongoDB()
    records = list(
        dao._get_collection("predictions")
        .find({"ts_code": ts_code})
        .sort("trade_date", -1)
        .limit(1)
    )
    dao.close()

    if not records:
        raise HTTPException(status_code=404, detail="No prediction found")

    r = records[0]
    return PredictResponse(
        ts_code=r["ts_code"],
        trade_date=r["trade_date"],
        model=r["model"],
        target_open=r.get("target_open"),
        target_close=r.get("target_close"),
        target_high=r.get("target_high"),
        target_low=r.get("target_low"),
    )


@router.post("", response_model=PredictResponse)
def create_prediction(request: PredictRequest):
    """Generate prediction."""
    result = do_predict(
        ts_code=request.ts_code,
        targets=request.targets,
        model=request.model,
        start_date=request.start_date,
        end_date=request.end_date,
    )

    if not result:
        raise HTTPException(status_code=400, detail="Prediction failed")

    prediction = get_prediction(request.ts_code)
    return prediction


@router.delete("/{ts_code}")
def delete_prediction(ts_code: str):
    """Delete predictions for a stock."""
    dao = MongoDB()
    result = dao._get_collection("predictions").delete_many({"ts_code": ts_code})
    dao.close()
    return {"deleted_count": result.deleted_count}
