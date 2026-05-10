"""Model management API endpoints."""

from fastapi import APIRouter, HTTPException
from trade_alpha.api.schemas import ModelCreateRequest, ModelResponse, PredictWithModelRequest
from trade_alpha.predict import model_service

router = APIRouter(prefix="/models", tags=["models"])


@router.post("", response_model=dict)
def create_model(request: ModelCreateRequest):
    """Create and train a new model."""
    try:
        model_id = model_service.create_model(
            name=request.name,
            model_type=request.model_type,
            ts_code=request.ts_code,
            targets=request.targets,
            params=request.params,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        return {"id": model_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[dict])
def list_models(model_type: str = None, ts_code: str = None):
    """List all models."""
    models = model_service.list_models(model_type=model_type, ts_code=ts_code)
    return [
        {
            "id": str(m["_id"]),
            "name": m["name"],
            "model_type": m["model_type"],
            "ts_code": m["ts_code"],
            "targets": m["targets"],
            "metrics": m["metrics"],
            "created_at": m["created_at"],
        }
        for m in models
    ]


@router.get("/{model_id}", response_model=ModelResponse)
def get_model(model_id: str):
    """Get model details."""
    model = model_service.get_model_by_id(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return ModelResponse(
        id=str(model["_id"]),
        name=model["name"],
        model_type=model["model_type"],
        ts_code=model["ts_code"],
        targets=model["targets"],
        params=model["params"],
        feature_cols=model["feature_cols"],
        train_date_range=model["train_date_range"],
        metrics=model["metrics"],
        created_at=model["created_at"],
        updated_at=model["updated_at"],
    )


@router.delete("/{model_id}")
def delete_model(model_id: str):
    """Delete a model."""
    deleted = model_service.delete_model(model_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"deleted": True}


@router.post("/{model_id}/predict")
def predict_with_model(model_id: str, request: PredictWithModelRequest = None):
    """Predict using a saved model."""
    try:
        ts_code = request.ts_code if request else None
        predictions = model_service.predict_with_model(model_id, ts_code)
        return {"model_id": model_id, "predictions": predictions}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
