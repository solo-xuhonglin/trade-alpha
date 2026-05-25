"""Model configuration API router."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from beanie import PydanticObjectId
from trade_alpha.constants import (
    DEFAULT_LABEL_MODE,
    DEFAULT_CLASSIFICATION_THRESHOLD_3D,
    DEFAULT_CLASSIFICATION_THRESHOLD_5D,
    DEFAULT_CLASSIFICATION_THRESHOLD_10D,
)
from trade_alpha.models import training

router = APIRouter(prefix="/model-configs", tags=["model-configs"])


class ConfigCreate(BaseModel):
    name: str
    model_type: str
    feature_fields: Optional[List[str]] = None
    standardize_fields: Optional[List[str]] = None
    winsorize_fields: Optional[List[str]] = None
    classification_horizons: Optional[List[int]] = None
    label_mode: str = DEFAULT_LABEL_MODE
    classification_threshold_3d: Optional[float] = None
    classification_threshold_5d: Optional[float] = None
    classification_threshold_10d: Optional[float] = None
    xgb_n_estimators: Optional[int] = None
    xgb_max_depth: Optional[int] = None
    xgb_learning_rate: Optional[float] = None
    xgb_min_child_weight: Optional[int] = None
    xgb_subsample: Optional[float] = None
    xgb_colsample_bytree: Optional[float] = None
    lstm_hidden_size: Optional[int] = None
    lstm_num_layers: Optional[int] = None
    lstm_dropout: Optional[float] = None
    lstm_epochs: Optional[int] = None
    lstm_batch_size: Optional[int] = None
    lstm_learning_rate: Optional[float] = None
    lstm_sequence_length: Optional[int] = None
    label_smoothing: Optional[float] = None
    early_stopping_patience: Optional[int] = None


class ConfigUpdate(BaseModel):
    name: Optional[str] = None
    feature_fields: Optional[List[str]] = None
    standardize_fields: Optional[List[str]] = None
    winsorize_fields: Optional[List[str]] = None
    classification_horizons: Optional[List[int]] = None
    label_mode: Optional[str] = None
    classification_threshold_3d: Optional[float] = None
    classification_threshold_5d: Optional[float] = None
    classification_threshold_10d: Optional[float] = None
    xgb_n_estimators: Optional[int] = None
    xgb_max_depth: Optional[int] = None
    xgb_learning_rate: Optional[float] = None
    xgb_min_child_weight: Optional[int] = None
    xgb_subsample: Optional[float] = None
    xgb_colsample_bytree: Optional[float] = None
    lstm_hidden_size: Optional[int] = None
    lstm_num_layers: Optional[int] = None
    lstm_dropout: Optional[float] = None
    lstm_epochs: Optional[int] = None
    lstm_batch_size: Optional[int] = None
    lstm_learning_rate: Optional[float] = None
    lstm_sequence_length: Optional[int] = None
    label_smoothing: Optional[float] = None
    early_stopping_patience: Optional[int] = None


def config_to_dict(c):
    """Convert ModelConfig to dict."""
    return {
        "id": str(c.id),
        "name": c.name,
        "model_type": c.model_type,
        "feature_fields": c.feature_fields,
        "standardize_fields": c.standardize_fields,
        "winsorize_fields": c.winsorize_fields,
        "classification_horizons": c.classification_horizons,
        "label_mode": c.label_mode,
        "classification_threshold_3d": c.classification_threshold_3d,
        "classification_threshold_5d": c.classification_threshold_5d,
        "classification_threshold_10d": c.classification_threshold_10d,
        "xgb_n_estimators": c.xgb_n_estimators,
        "xgb_max_depth": c.xgb_max_depth,
        "xgb_learning_rate": c.xgb_learning_rate,
        "xgb_min_child_weight": c.xgb_min_child_weight,
        "xgb_subsample": c.xgb_subsample,
        "xgb_colsample_bytree": c.xgb_colsample_bytree,
        "lstm_hidden_size": c.lstm_hidden_size,
        "lstm_num_layers": c.lstm_num_layers,
        "lstm_dropout": c.lstm_dropout,
        "lstm_epochs": c.lstm_epochs,
        "lstm_batch_size": c.lstm_batch_size,
        "lstm_learning_rate": c.lstm_learning_rate,
        "lstm_sequence_length": c.lstm_sequence_length,
        "label_smoothing": c.label_smoothing,
        "early_stopping_patience": c.early_stopping_patience,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


@router.post("")
async def create_config(body: ConfigCreate):
    """Create model configuration."""
    try:
        c = await training.create_config(
            name=body.name,
            model_type=body.model_type,
            feature_fields=body.feature_fields,
            standardize_fields=body.standardize_fields,
            winsorize_fields=body.winsorize_fields,
            classification_horizons=body.classification_horizons,
            label_mode=body.label_mode,
            classification_threshold_3d=body.classification_threshold_3d or DEFAULT_CLASSIFICATION_THRESHOLD_3D,
            classification_threshold_5d=body.classification_threshold_5d or DEFAULT_CLASSIFICATION_THRESHOLD_5D,
            classification_threshold_10d=body.classification_threshold_10d or DEFAULT_CLASSIFICATION_THRESHOLD_10D,
            xgb_n_estimators=body.xgb_n_estimators or 100,
            xgb_max_depth=body.xgb_max_depth or 6,
            xgb_learning_rate=body.xgb_learning_rate or 0.1,
            xgb_min_child_weight=body.xgb_min_child_weight or 1,
            xgb_subsample=body.xgb_subsample or 1.0,
            xgb_colsample_bytree=body.xgb_colsample_bytree or 1.0,
            lstm_hidden_size=body.lstm_hidden_size or 64,
            lstm_num_layers=body.lstm_num_layers or 2,
            lstm_dropout=body.lstm_dropout or 0.2,
            lstm_epochs=body.lstm_epochs or 25,
            lstm_batch_size=body.lstm_batch_size or 256,
            lstm_learning_rate=body.lstm_learning_rate or 0.001,
            lstm_sequence_length=body.lstm_sequence_length or 60,
            label_smoothing=body.label_smoothing or 0.1,
            early_stopping_patience=body.early_stopping_patience or 5,
        )
        return config_to_dict(c)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
async def list_configs(model_type: str = Query(None)):
    """List model configurations."""
    configs = await training.list_configs(model_type=model_type)
    return [config_to_dict(c) for c in configs]


@router.get("/{config_id}")
async def get_config(config_id: str):
    """Get model configuration by ID."""
    try:
        obj_id = PydanticObjectId(config_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid config ID")

    c = await training.get_config_by_id(obj_id)
    if not c:
        raise HTTPException(status_code=404, detail="Config not found")
    return config_to_dict(c)


@router.put("/{config_id}")
async def update_config(config_id: str, body: ConfigUpdate):
    """Update model configuration."""
    try:
        obj_id = PydanticObjectId(config_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid config ID")

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        c = await training.update_config(obj_id, **update_data)
        if not c:
            raise HTTPException(status_code=404, detail="Config not found")
        return config_to_dict(c)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{config_id}")
async def delete_config(config_id: str):
    """Delete model configuration and cascade delete trainings."""
    try:
        obj_id = PydanticObjectId(config_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid config ID")

    deleted = await training.delete_config(obj_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Config not found")
    return {"deleted": True}
