"""Training DAO module."""

from typing import Any, Optional
from bson import ObjectId
from trade_alpha.dao.mongodb import MongoDB


class TrainingDAO:
    """DAO for trainings collection."""

    def __init__(self, db: MongoDB | None = None):
        self.db = db or MongoDB()
        self.collection = "trainings"

    def insert(self, doc: dict[str, Any]) -> str:
        """Insert training document.

        Args:
            doc: Training document

        Returns:
            Inserted ID as string
        """
        coll = self.db._get_collection(self.collection)
        result = coll.insert_one(doc)
        return str(result.inserted_id)

    def find_by_id(self, training_id: str) -> Optional[dict[str, Any]]:
        """Find training by ID.

        Args:
            training_id: Training ID

        Returns:
            Training document or None
        """
        results = self.db.find_generic(
            {"_id": ObjectId(training_id)},
            self.collection,
            projection=None,
        )
        return results[0] if results else None

    def find_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """Find training by name.

        Args:
            name: Training name

        Returns:
            Training document or None
        """
        results = self.db.find_generic(
            {"name": name},
            self.collection,
            projection=None,
        )
        return results[0] if results else None

    def find_all(self, config_id: str | None = None) -> list[dict[str, Any]]:
        """Find all trainings.

        Args:
            config_id: Optional filter by config ID

        Returns:
            List of training documents
        """
        query = {}
        if config_id:
            query["config_id"] = ObjectId(config_id)
        return self.db.find_generic(query, self.collection, projection=None)

    def update(self, training_id: str, update_doc: dict[str, Any]) -> bool:
        """Update training.

        Args:
            training_id: Training ID
            update_doc: Update document

        Returns:
            True if modified
        """
        coll = self.db._get_collection(self.collection)
        result = coll.update_one(
            {"_id": ObjectId(training_id)},
            {"$set": update_doc}
        )
        return result.modified_count > 0

    def delete(self, training_id: str) -> bool:
        """Delete training.

        Args:
            training_id: Training ID

        Returns:
            True if deleted
        """
        return self.db.delete_generic(
            {"_id": ObjectId(training_id)},
            self.collection
        ) > 0

    def delete_by_config_id(self, config_id: str) -> int:
        """Delete all trainings for a config.

        Args:
            config_id: Config ID

        Returns:
            Number of trainings deleted
        """
        return self.db.delete_generic(
            {"config_id": ObjectId(config_id)},
            self.collection
        )
