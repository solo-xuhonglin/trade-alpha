"""Model configuration service."""

from datetime import datetime
from typing import Optional, List
from beanie import PydanticObjectId
from trade_alpha.dao import ModelConfig, Training
from trade_alpha.logging import get_logger

logger = get_logger("config_service")


async def create_config(
    name: str,
    model_type: str,
    params: dict,
    targets: List[str],
) -> ModelConfig:
    """Create model configuration."""
    logger.info(f"Creating config: {name} ({model_type})")
    
    existing = await ModelConfig.find_one(ModelConfig.name == name)
    if existing:
        raise ValueError(f"Config already exists: {name}")
    
    valid_types = ["linear", "xgboost", "lstm"]
    if model_type not in valid_types:
        raise ValueError(f"Invalid model_type: {model_type}")
    
    config = ModelConfig(
        name=name,
        model_type=model_type,
        params=params,
        targets=targets,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    await config.insert()
    logger.info(f"Config created: id={config.id}")
    return config


async def get_config_by_id(config_id: PydanticObjectId) -> Optional[ModelConfig]:
    """Get configuration by ID."""
    return await ModelConfig.get(config_id)


async def get_config_by_name(name: str) -> Optional[ModelConfig]:
    """Get configuration by name."""
    return await ModelConfig.find_one(ModelConfig.name == name)


async def list_configs(model_type: str = None) -> List[ModelConfig]:
    """List configurations with optional filter."""
    if model_type:
        return await ModelConfig.find(
            ModelConfig.model_type == model_type
        ).to_list()
    return await ModelConfig.find_all().to_list()


async def update_config(config_id: PydanticObjectId, **kwargs) -> Optional[ModelConfig]:
    """Update configuration."""
    config = await ModelConfig.get(config_id)
    if not config:
        return None
    
    if "name" in kwargs:
        existing = await ModelConfig.find_one(ModelConfig.name == kwargs["name"])
        if existing and existing.id != config_id:
            raise ValueError(f"Config name already exists: {kwargs['name']}")
    
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    
    config.updated_at = datetime.utcnow()
    await config.save()
    logger.info(f"Config updated: id={config_id}")
    return config


async def delete_config(config_id: PydanticObjectId) -> bool:
    """Delete configuration and cascade delete trainings."""
    config = await ModelConfig.get(config_id)
    if not config:
        return False
    
    await Training.find(Training.config_id == config_id).delete()
    
    await config.delete()
    logger.info(f"Config deleted: id={config_id}")
    return True
