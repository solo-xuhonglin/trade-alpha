"""Model configuration API router."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from beanie import PydanticObjectId
from trade_alpha.predict import config_service

router = APIRouter(prefix="/model-configs", tags=["model-configs"])


class ConfigCreate(BaseModel):
    name: str
    model_type: str
    feature_fields: Optional[List[str]] = None
    standardize_fields: Optional[List[str]] = None
    winsorize_fields: Optional[List[str]] = None
    output_fields: Optional[List[str]] = None
    classification_horizons: Optional[List[int]] = None
    classification_threshold: Optional[float] = None


class ConfigUpdate(BaseModel):
    name: Optional[str] = None
    feature_fields: Optional[List[str]] = None
    standardize_fields: Optional[List[str]] = None
    winsorize_fields: Optional[List[str]] = None
    output_fields: Optional[List[str]] = None
    classification_horizons: Optional[List[int]] = None
    classification_threshold: Optional[float] = None


@router.post("")
async def create_config(body: ConfigCreate):
    """Create model configuration."""
    try:
        c = await config_service.create_config(
            name=body.name,
            model_type=body.model_type,
            feature_fields=body.feature_fields,
            standardize_fields=body.standardize_fields,
            winsorize_fields=body.winsorize_fields,
            output_fields=body.output_fields,
            classification_horizons=body.classification_horizons,
            classification_threshold=body.classification_threshold or 0.02,
        )
        return {
            "id": str(c.id),
            "name": c.name,
            "model_type": c.model_type,
            "feature_fields": c.feature_fields,
            "standardize_fields": c.standardize_fields,
            "winsorize_fields": c.winsorize_fields,
            "output_fields": c.output_fields,
            "classification_horizons": c.classification_horizons,
            "classification_threshold": c.classification_threshold,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
async def list_configs(model_type: str = Query(None)):
    """List model configurations."""
    configs = await config_service.list_configs(model_type=model_type)
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "model_type": c.model_type,
            "feature_fields": c.feature_fields,
            "standardize_fields": c.standardize_fields,
            "winsorize_fields": c.winsorize_fields,
            "output_fields": c.output_fields,
            "classification_horizons": c.classification_horizons,
            "classification_threshold": c.classification_threshold,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        }
        for c in configs
    ]


@router.get("/{config_id}")
async def get_config(config_id: str):
    """Get model configuration by ID."""
    try:
        obj_id = PydanticObjectId(config_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid config ID")

    c = await config_service.get_config_by_id(obj_id)
    if not c:
        raise HTTPException(status_code=404, detail="Config not found")
    return {
        "id": str(c.id),
        "name": c.name,
        "model_type": c.model_type,
        "feature_fields": c.feature_fields,
        "standardize_fields": c.standardize_fields,
        "winsorize_fields": c.winsorize_fields,
        "output_fields": c.output_fields,
        "classification_horizons": c.classification_horizons,
        "classification_threshold": c.classification_threshold,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


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
        c = await config_service.update_config(obj_id, **update_data)
        if not c:
            raise HTTPException(status_code=404, detail="Config not found")
        return {
            "id": str(c.id),
            "name": c.name,
            "model_type": c.model_type,
            "feature_fields": c.feature_fields,
            "standardize_fields": c.standardize_fields,
            "winsorize_fields": c.winsorize_fields,
            "output_fields": c.output_fields,
            "classification_horizons": c.classification_horizons,
            "classification_threshold": c.classification_threshold,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{config_id}")
async def delete_config(config_id: str):
    """Delete model configuration and cascade delete trainings."""
    try:
        obj_id = PydanticObjectId(config_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid config ID")

    deleted = await config_service.delete_config(obj_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Config not found")
    return {"deleted": True}
