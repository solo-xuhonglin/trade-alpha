"""Predict API endpoints."""

from fastapi import APIRouter, HTTPException
from trade_alpha.api.schemas import PredictRequest
from trade_alpha.predict.service import (
    predict as do_predict,
    get_prediction_by_ts_code,
    delete_predictions_by_ts_code,
)

router = APIRouter(prefix="/predict", tags=["predict"])


@router.get("/{ts_code}")
async def get_prediction(ts_code: str):
    """Get latest prediction for a stock."""
    prediction = await get_prediction_by_ts_code(ts_code)

    if not prediction:
        raise HTTPException(status_code=404, detail="No prediction found")

    return prediction


@router.post("")
async def create_prediction(request: PredictRequest):
    """Generate prediction."""
    predictions = await do_predict(
        ts_code=request.ts_code,
        targets=request.targets,
        model=request.model,
        start_date=request.start_date,
        end_date=request.end_date,
    )

    if not predictions:
        raise HTTPException(status_code=400, detail="Prediction failed")

    prediction = await get_prediction_by_ts_code(request.ts_code)
    return prediction


@router.delete("/{ts_code}")
async def delete_prediction(ts_code: str):
    """Delete predictions for a stock."""
    deleted_count = await delete_predictions_by_ts_code(ts_code)
    return {"deleted_count": deleted_count}
