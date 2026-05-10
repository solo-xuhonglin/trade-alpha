"""Model configuration API router."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from trade_alpha.predict import config_service

router = APIRouter(prefix="/model-configs", tags=["model-configs"])


class ConfigCreate(BaseModel):
    name: str
    model_type: str
    params: Dict[str, Any] = {}
    targets: List[str]


class ConfigUpdate(BaseModel):
    name: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    targets: Optional[List[str]] = None


class ConfigResponse(BaseModel):
    id: str
    name: str
    model_type: str
    params: Dict[str, Any]
    targets: List[str]


@router.post("", response_model=ConfigResponse)
def create_config(body: ConfigCreate):
    """Create model configuration."""
    try:
        config_id = config_service.create_config(
            name=body.name,
            model_type=body.model_type,
            params=body.params,
            targets=body.targets,
        )
        config = config_service.get_config_by_id(config_id)
        return ConfigResponse(
            id=str(config["_id"]),
            name=config["name"],
            model_type=config["model_type"],
            params=config["params"],
            targets=config["targets"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[ConfigResponse])
def list_configs(model_type: str = None):
    """List model configurations."""
    configs = config_service.list_configs(model_type=model_type)
    return [
        ConfigResponse(
            id=str(c["_id"]),
            name=c["name"],
            model_type=c["model_type"],
            params=c["params"],
            targets=c["targets"],
        )
        for c in configs
    ]


@router.get("/{config_id}", response_model=ConfigResponse)
def get_config(config_id: str):
    """Get model configuration by ID."""
    config = config_service.get_config_by_id(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    return ConfigResponse(
        id=str(config["_id"]),
        name=config["name"],
        model_type=config["model_type"],
        params=config["params"],
        targets=config["targets"],
    )


@router.put("/{config_id}", response_model=ConfigResponse)
def update_config(config_id: str, body: ConfigUpdate):
    """Update model configuration."""
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        config_service.update_config(config_id, **update_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    config = config_service.get_config_by_id(config_id)
    return ConfigResponse(
        id=str(config["_id"]),
        name=config["name"],
        model_type=config["model_type"],
        params=config["params"],
        targets=config["targets"],
    )


@router.delete("/{config_id}")
def delete_config(config_id: str):
    """Delete model configuration and cascade delete trainings."""
    deleted = config_service.delete_config(config_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Config not found")
    return {"deleted": True}
