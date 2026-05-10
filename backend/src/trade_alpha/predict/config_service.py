"""Model configuration service."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from bson import ObjectId
from trade_alpha.dao import MongoDB


COLLECTION = "model_configs"


def create_config(
    name: str,
    model_type: str,
    params: Dict[str, Any],
    targets: List[str],
) -> str:
    """Create model configuration.

    Args:
        name: Configuration name (unique)
        model_type: Model type (linear/xgboost/lstm)
        params: Model parameters
        targets: Target columns to predict

    Returns:
        Configuration ID
    """
    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    existing = collection.find_one({"name": name})
    if existing:
        dao.close()
        raise ValueError(f"Config already exists: {name}")

    valid_types = ["linear", "xgboost", "lstm"]
    if model_type not in valid_types:
        dao.close()
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
    dao.close()
    return str(result.inserted_id)


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
    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    query = {}
    if model_type:
        query["model_type"] = model_type

    results = list(collection.find(query))
    dao.close()
    return results


def update_config(config_id: str, **kwargs) -> bool:
    """Update configuration."""
    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    if "name" in kwargs:
        existing = collection.find_one({"name": kwargs["name"], "_id": {"$ne": ObjectId(config_id)}})
        if existing:
            dao.close()
            raise ValueError(f"Config name already exists: {kwargs['name']}")

    kwargs["updated_at"] = datetime.utcnow()
    result = collection.update_one(
        {"_id": ObjectId(config_id)},
        {"$set": kwargs}
    )
    dao.close()
    return result.modified_count > 0


def delete_config(config_id: str) -> bool:
    """Delete configuration and cascade delete trainings."""
    from trade_alpha.predict.training_service import delete_trainings_by_config

    dao = MongoDB()
    collection = dao._get_collection(COLLECTION)

    config = collection.find_one({"_id": ObjectId(config_id)})
    if not config:
        dao.close()
        return False

    delete_trainings_by_config(config_id)

    result = collection.delete_one({"_id": ObjectId(config_id)})
    dao.close()
    return result.deleted_count > 0
