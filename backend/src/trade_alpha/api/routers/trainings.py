"""Training API router."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
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


class TrainingResponse(BaseModel):
    id: str
    config_id: str
    name: str
    ts_codes: List[str]
    start_date: str
    end_date: str
    metrics: Dict[str, Any]


@router.post("", response_model=TrainingResponse)
def create_training(body: TrainingCreate):
    """Create training."""
    try:
        training_id = training_service.create_training(
            config_id=body.config_id,
            name=body.name,
            ts_codes=body.ts_codes,
            start_date=body.start_date,
            end_date=body.end_date,
        )
        training = training_service.get_training_by_id(training_id)
        return TrainingResponse(
            id=str(training["_id"]),
            config_id=str(training["config_id"]),
            name=training["name"],
            ts_codes=training["ts_codes"],
            start_date=training["start_date"],
            end_date=training["end_date"],
            metrics=training["metrics"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[TrainingResponse])
def list_trainings(config_id: str = None):
    """List trainings."""
    trainings = training_service.list_trainings(config_id=config_id)
    return [
        TrainingResponse(
            id=str(t["_id"]),
            config_id=str(t["config_id"]),
            name=t["name"],
            ts_codes=t["ts_codes"],
            start_date=t["start_date"],
            end_date=t["end_date"],
            metrics=t["metrics"],
        )
        for t in trainings
    ]


@router.get("/{training_id}", response_model=TrainingResponse)
def get_training(training_id: str):
    """Get training by ID."""
    training = training_service.get_training_by_id(training_id)
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")
    return TrainingResponse(
        id=str(training["_id"]),
        config_id=str(training["config_id"]),
        name=training["name"],
        ts_codes=training["ts_codes"],
        start_date=training["start_date"],
        end_date=training["end_date"],
        metrics=training["metrics"],
    )


@router.delete("/{training_id}")
def delete_training(training_id: str):
    """Delete training."""
    deleted = training_service.delete_training(training_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Training not found")
    return {"deleted": True}


@router.post("/{training_id}/predict")
def predict(training_id: str, body: PredictRequest = None):
    """Predict using trained model."""
    try:
        ts_code = body.ts_code if body else None
        predictions = training_service.predict_with_training(training_id, ts_code)
        return {"predictions": predictions}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
