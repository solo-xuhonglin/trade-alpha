"""Model configuration service."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from bson import ObjectId
from trade_alpha.dao import MongoDB
from trade_alpha.logging import get_logger

logger = get_logger("config_service")

COLLECTION = "model_configs"


def create_config(
    name: str,
    model_type: str,
    params: Dict[str, Any],
    targets: List[str],
) -> str:
    """Create model configuration."""
    logger.info("create_config", f"Creating config: {name} ({model_type})")

    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    existing = collection.find_one({"name": name})
    if existing:
        dao.close()
        logger.warning("create_config", f"Config already exists: {name}")
        raise ValueError(f"Config already exists: {name}")

    valid_types = ["linear", "xgboost", "lstm"]
    if model_type not in valid_types:
        dao.close()
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

    result = collection.insert_one(config)
    config_id = str(result.inserted_id)
    dao.close()
    logger.info("create_config", f"Config created: {config_id}")
    return config_id


def get_config_by_id(config_id: str) -> Optional[Dict]:
    """Get configuration by ID."""
    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)
    result = collection.find_one({"_id": ObjectId(config_id)})
    dao.close()
    return result


def get_config_by_name(name: str) -> Optional[Dict]:
    """Get configuration by name."""
    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)
    result = collection.find_one({"name": name})
    dao.close()
    return result


def list_configs(model_type: str = None) -> List[Dict]:
    """List configurations with optional filter."""
    logger.debug("list_configs", f"Listing configs (type={model_type})")

    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    query = {}
    if model_type:
        query["model_type"] = model_type

    results = list(collection.find(query))
    dao.close()
    logger.debug("list_configs", f"Found {len(results)} configs")
    return results


def update_config(config_id: str, **kwargs) -> bool:
    """Update configuration."""
    logger.info("update_config", f"Updating config: {config_id}")

    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    if "name" in kwargs:
        existing = collection.find_one({"name": kwargs["name"], "_id": {"$ne": ObjectId(config_id)}})
        if existing:
            dao.close()
            logger.warning("update_config", f"Config name already exists: {kwargs['name']}")
            raise ValueError(f"Config name already exists: {kwargs['name']}")

    kwargs["updated_at"] = datetime.utcnow()
    result = collection.update_one(
        {"_id": ObjectId(config_id)},
        {"$set": kwargs}
    )
    dao.close()
    success = result.modified_count > 0
    logger.info("update_config", f"Config {config_id} updated: {success}")
    return success


def delete_config(config_id: str) -> bool:
    """Delete configuration and cascade delete trainings."""
    from trade_alpha.predict.training_service import delete_trainings_by_config

    logger.info("delete_config", f"Deleting config: {config_id}")

    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    config = collection.find_one({"_id": ObjectId(config_id)})
    if not config:
        dao.close()
        logger.warning("delete_config", f"Config not found: {config_id}")
        return False

    delete_trainings_by_config(config_id)

    result = collection.delete_one({"_id": ObjectId(config_id)})
    dao.close()
    success = result.deleted_count > 0
    logger.info("delete_config", f"Config {config_id} deleted: {success}")
    return success
