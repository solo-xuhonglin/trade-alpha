"""Portfolio DAO module."""

from typing import Any, Optional
from bson import ObjectId
from trade_alpha.dao.mongodb import MongoDB


class PortfolioDAO:
    """DAO for portfolios collection."""

    def __init__(self, db: MongoDB | None = None):
        self.db = db or MongoDB()
        self.collection = "portfolios"

    def insert(self, doc: dict[str, Any]) -> str:
        """Insert portfolio document.

        Args:
            doc: Portfolio document

        Returns:
            Inserted ID as string
        """
        coll = self.db._get_collection(self.collection)
        result = coll.insert_one(doc)
        return str(result.inserted_id)

    def find_by_id(self, portfolio_id: str) -> Optional[dict[str, Any]]:
        """Find portfolio by ID.

        Args:
            portfolio_id: Portfolio ID

        Returns:
            Portfolio document or None
        """
        results = self.db.find_generic(
            {"_id": ObjectId(portfolio_id)},
            self.collection,
            projection=None,
        )
        return results[0] if results else None

    def find_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """Find portfolio by name.

        Args:
            name: Portfolio name

        Returns:
            Portfolio document or None
        """
        results = self.db.find_generic(
            {"name": name},
            self.collection,
            projection=None,
        )
        return results[0] if results else None

    def find_all(self) -> list[dict[str, Any]]:
        """Find all portfolios.

        Returns:
            List of portfolio documents
        """
        return self.db.find_generic({}, self.collection, projection=None)

    def update(self, portfolio_id: str, update_doc: dict[str, Any]) -> bool:
        """Update portfolio.

        Args:
            portfolio_id: Portfolio ID
            update_doc: Update document

        Returns:
            True if modified
        """
        coll = self.db._get_collection(self.collection)
        result = coll.update_one(
            {"_id": ObjectId(portfolio_id)},
            {"$set": update_doc}
        )
        return result.modified_count > 0

    def delete(self, portfolio_id: str) -> bool:
        """Delete portfolio.

        Args:
            portfolio_id: Portfolio ID

        Returns:
            True if deleted
        """
        return self.db.delete_generic(
            {"_id": ObjectId(portfolio_id)},
            self.collection
        ) > 0
