"""Model config DAO module."""

from typing import Any, Optional
from bson import ObjectId
from trade_alpha.dao.mongodb import MongoDB


class ModelConfigDAO:
    """DAO for model_configs collection."""

    def __init__(self, db: MongoDB | None = None):
        self.db = db or MongoDB()
        self.collection = "model_configs"

    def insert(self, doc: dict[str, Any]) -> str:
        """Insert model config document.

        Args:
            doc: Model config document

        Returns:
            Inserted ID as string
        """
        coll = self.db._get_collection(self.collection)
        result = coll.insert_one(doc)
        return str(result.inserted_id)

    def find_by_id(self, config_id: str) -> Optional[dict[str, Any]]:
        """Find model config by ID.

        Args:
            config_id: Model config ID

        Returns:
            Model config document or None
        """
        results = self.db.find_generic(
            {"_id": ObjectId(config_id)},
            self.collection,
        )
        return results[0] if results else None

    def find_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """Find model config by name.

        Args:
            name: Model config name

        Returns:
            Model config document or None
        """
        results = self.db.find_generic(
            {"name": name},
            self.collection,
        )
        return results[0] if results else None

    def find_all(self, model_type: str | None = None) -> list[dict[str, Any]]:
        """Find all model configs.

        Args:
            model_type: Optional filter by model type

        Returns:
            List of model config documents
        """
        query = {}
        if model_type:
            query["model_type"] = model_type
        return self.db.find_generic(query, self.collection)

    def update(self, config_id: str, update_doc: dict[str, Any]) -> bool:
        """Update model config.

        Args:
            config_id: Model config ID
            update_doc: Update document

        Returns:
            True if modified
        """
        coll = self.db._get_collection(self.collection)
        result = coll.update_one(
            {"_id": ObjectId(config_id)},
            {"$set": update_doc}
        )
        return result.modified_count > 0

    def delete(self, config_id: str) -> bool:
        """Delete model config.

        Args:
            config_id: Model config ID

        Returns:
            True if deleted
        """
        return self.db.delete_generic(
            {"_id": ObjectId(config_id)},
            self.collection
        ) > 0

    def name_exists(self, name: str, exclude_id: str | None = None) -> bool:
        """Check if name already exists.

        Args:
            name: Name to check
            exclude_id: ID to exclude from check

        Returns:
            True if name exists
        """
        query = {"name": name}
        if exclude_id:
            query["_id"] = {"$ne": ObjectId(exclude_id)}
        results = self.db.find_generic(query, self.collection, projection=None)
        return len(results) > 0
