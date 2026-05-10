"""Strategy DAO module."""

from typing import Any, Optional
from bson import ObjectId
from trade_alpha.dao.mongodb import MongoDB


class StrategyDAO:
    """DAO for strategies collection."""

    def __init__(self, db: MongoDB | None = None):
        self.db = db or MongoDB()
        self.collection = "strategies"

    def insert(self, doc: dict[str, Any]) -> str:
        """Insert strategy document.

        Args:
            doc: Strategy document

        Returns:
            Inserted ID as string
        """
        coll = self.db._get_collection(self.collection)
        result = coll.insert_one(doc)
        return str(result.inserted_id)

    def find_by_id(self, strategy_id: str) -> Optional[dict[str, Any]]:
        """Find strategy by ID.

        Args:
            strategy_id: Strategy ID

        Returns:
            Strategy document or None
        """
        results = self.db.find_generic(
            {"_id": ObjectId(strategy_id)},
            self.collection,
            projection=None,
        )
        return results[0] if results else None

    def find_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """Find strategy by name.

        Args:
            name: Strategy name

        Returns:
            Strategy document or None
        """
        results = self.db.find_generic(
            {"name": name},
            self.collection,
            projection=None,
        )
        return results[0] if results else None

    def find_all(self) -> list[dict[str, Any]]:
        """Find all strategies.

        Returns:
            List of strategy documents
        """
        return self.db.find_generic({}, self.collection, projection=None)

    def update(self, strategy_id: str, update_doc: dict[str, Any]) -> bool:
        """Update strategy.

        Args:
            strategy_id: Strategy ID
            update_doc: Update document

        Returns:
            True if modified
        """
        coll = self.db._get_collection(self.collection)
        result = coll.update_one(
            {"_id": ObjectId(strategy_id)},
            {"$set": update_doc}
        )
        return result.modified_count > 0

    def delete(self, strategy_id: str) -> bool:
        """Delete strategy.

        Args:
            strategy_id: Strategy ID

        Returns:
            True if deleted
        """
        return self.db.delete_generic(
            {"_id": ObjectId(strategy_id)},
            self.collection
        ) > 0
