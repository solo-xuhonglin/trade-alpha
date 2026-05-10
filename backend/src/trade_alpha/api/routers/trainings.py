"""Training API router."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from beanie import PydanticObjectId
from trade_alpha.predict import training_service

router = APIRouter(prefix="/trainings", tags=["trainings"])


class TrainingCreate(BaseModel):
    config_id: str
    name: str
    ts_codes: List[str]
    start_date: str
    end_date: str


class PredictRequest(BaseModel):
    ts_code: Optional[str] = None


@router.post("")
async def create_training(body: TrainingCreate):
    """Create training."""
    try:
        config_id = PydanticObjectId(body.config_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid config ID format")
    
    try:
        return await training_service.create_training(
            config_id=config_id,
            name=body.name,
            ts_codes=body.ts_codes,
            start_date=body.start_date,
            end_date=body.end_date,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
async def list_trainings(config_id: str = Query(None)):
    """List trainings."""
    if config_id:
        try:
            c_id = PydanticObjectId(config_id)
            return await training_service.list_trainings(config_id=c_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid config ID format")
    return await training_service.list_trainings()


@router.get("/{training_id}")
async def get_training(training_id: str):
    """Get training by ID."""
    try:
        obj_id = PydanticObjectId(training_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid training ID")
    
    training = await training_service.get_training_by_id(obj_id)
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")
    return training


@router.delete("/{training_id}")
async def delete_training(training_id: str):
    """Delete training."""
    try:
        obj_id = PydanticObjectId(training_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid training ID")
    
    deleted = await training_service.delete_training(obj_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Training not found")
    return {"deleted": True}


@router.post("/{training_id}/predict")
async def predict(training_id: str, body: PredictRequest = None):
    """Predict using trained model."""
    try:
        obj_id = PydanticObjectId(training_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid training ID")
    
    try:
        ts_code = body.ts_code if body else None
        predictions = await training_service.predict_with_training(obj_id, ts_code)
        return {"predictions": predictions}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
