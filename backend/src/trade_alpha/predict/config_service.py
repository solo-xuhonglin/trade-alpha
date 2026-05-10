"""Model configuration service."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from trade_alpha.dao import ModelConfigDAO, TrainingDAO
from trade_alpha.logging import get_logger

logger = get_logger("config_service")


def create_config(
    name: str,
    model_type: str,
    params: Dict[str, Any],
    targets: List[str],
) -> str:
    """Create model configuration."""
    logger.info("create_config", f"Creating config: {name} ({model_type})")

    dao = ModelConfigDAO()

    if dao.find_by_name(name):
        logger.warning("create_config", f"Config already exists: {name}")
        raise ValueError(f"Config already exists: {name}")

    valid_types = ["linear", "xgboost", "lstm"]
    if model_type not in valid_types:
        logger.warning("create_config", f"Invalid model_type: {model_type}")
        raise ValueError(f"Invalid model_type: {model_type}")

    config = {
        "name": name,
        "model_type": model_type,
        "params": params,
        "targets": targets,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    config_id = dao.insert(config)
    logger.info("create_config", f"Config created: {config_id}")
    return config_id


def get_config_by_id(config_id: str) -> Optional[Dict]:
    """Get configuration by ID."""
    dao = ModelConfigDAO()
    return dao.find_by_id(config_id)


def get_config_by_name(name: str) -> Optional[Dict]:
    """Get configuration by name."""
    dao = ModelConfigDAO()
    return dao.find_by_name(name)


def list_configs(model_type: str = None) -> List[Dict]:
    """List configurations with optional filter."""
    logger.debug("list_configs", f"Listing configs (type={model_type})")

    dao = ModelConfigDAO()
    results = dao.find_all(model_type)
    logger.debug("list_configs", f"Found {len(results)} configs")
    return results


def update_config(config_id: str, **kwargs) -> bool:
    """Update configuration."""
    logger.info("update_config", f"Updating config: {config_id}")

    dao = ModelConfigDAO()

    if "name" in kwargs:
        if dao.name_exists(kwargs["name"], exclude_id=config_id):
            logger.warning("update_config", f"Config name already exists: {kwargs['name']}")
            raise ValueError(f"Config name already exists: {kwargs['name']}")

    kwargs["updated_at"] = datetime.utcnow()
    success = dao.update(config_id, kwargs)
    logger.info("update_config", f"Config {config_id} updated: {success}")
    return success


def delete_config(config_id: str) -> bool:
    """Delete configuration and cascade delete trainings."""
    logger.info("delete_config", f"Deleting config: {config_id}")

    dao = ModelConfigDAO()
    training_dao = TrainingDAO()

    if not dao.find_by_id(config_id):
        logger.warning("delete_config", f"Config not found: {config_id}")
        return False

    training_dao.delete_by_config_id(config_id)

    success = dao.delete(config_id)
    logger.info("delete_config", f"Config {config_id} deleted: {success}")
    return success
