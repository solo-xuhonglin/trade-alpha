"""Predict API endpoints."""

from fastapi import APIRouter, HTTPException
from beanie import PydanticObjectId
from trade_alpha.predict import training_service

router = APIRouter(prefix="/predict", tags=["predict"])


@router.get("/{prediction_id}")
async def get_prediction(prediction_id: str):
    """Get prediction by ID."""
    try:
        obj_id = PydanticObjectId(prediction_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid prediction ID")

    prediction = await training_service.get_prediction_by_id(obj_id)
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")

    return prediction


@router.delete("/{prediction_id}")
async def delete_prediction(prediction_id: str):
    """Delete prediction by ID."""
    try:
        obj_id = PydanticObjectId(prediction_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid prediction ID")

    deleted = await training_service.delete_prediction(obj_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Prediction not found")

    return {"deleted": True}
