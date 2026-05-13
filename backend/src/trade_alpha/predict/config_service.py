"""Model configuration service."""

from datetime import datetime, timezone
from typing import Optional, List
from beanie import PydanticObjectId
from trade_alpha.dao import ModelConfig, TrainingResult
from trade_alpha.logging import get_logger

logger = get_logger("config_service")


async def create_config(
    name: str,
    model_type: str,
    feature_fields: Optional[List[str]] = None,
    classification_horizons: Optional[List[int]] = None,
    classification_threshold: float = 0.02,
    normalizer_fields: Optional[dict] = None,
) -> ModelConfig:
    """Create model configuration."""
    if not name:
        raise ValueError("name is required")
    if model_type not in ("xgboost", "lstm"):
        raise ValueError(f"model_type must be xgboost or lstm, got: {model_type}")

    existing = await ModelConfig.find_one(ModelConfig.name == name)
    if existing:
        raise ValueError(f"Config already exists: {name}")

    config = ModelConfig(
        name=name,
        model_type=model_type,
        feature_fields=feature_fields or [],
        classification_horizons=classification_horizons or [3, 5],
        classification_threshold=classification_threshold,
        normalizer_fields=normalizer_fields or {},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await config.insert()
    logger.info(f"Config created: id={config.id} name={name} model_type={model_type}")
    return config


async def get_config_by_id(config_id: PydanticObjectId) -> Optional[ModelConfig]:
    return await ModelConfig.get(config_id)


async def get_config_by_name(name: str) -> Optional[ModelConfig]:
    return await ModelConfig.find_one(ModelConfig.name == name)


async def list_configs(model_type: str = None) -> List[ModelConfig]:
    if model_type:
        return await ModelConfig.find(ModelConfig.model_type == model_type).to_list()
    return await ModelConfig.find_all().to_list()


async def update_config(config_id: PydanticObjectId, **kwargs) -> Optional[ModelConfig]:
    config = await ModelConfig.get(config_id)
    if not config:
        return None
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    config.updated_at = datetime.now(timezone.utc)
    await config.save()
    return config


async def delete_config(config_id: PydanticObjectId) -> bool:
    config = await ModelConfig.get(config_id)
    if not config:
        return False
    await TrainingResult.find(TrainingResult.config_id == config_id).delete()
    await config.delete()
    logger.info(f"Config deleted: id={config_id}")
    return True
