"""Backtest DAO module."""

from typing import Any, Optional
from bson import ObjectId
from pymongo import DESCENDING
from trade_alpha.dao.mongodb import MongoDB


class BacktestDAO:
    """DAO for backtests collection."""

    def __init__(self, db: MongoDB | None = None):
        self.db = db or MongoDB()
        self.collection = "backtests"

    def insert(self, doc: dict[str, Any]) -> str:
        """Insert backtest document.

        Args:
            doc: Backtest document

        Returns:
            Inserted ID as string
        """
        coll = self.db._get_collection(self.collection)
        result = coll.insert_one(doc)
        return str(result.inserted_id)

    def find_by_id(self, backtest_id: str) -> Optional[dict[str, Any]]:
        """Find backtest by ID.

        Args:
            backtest_id: Backtest ID

        Returns:
            Backtest document or None
        """
        results = self.db.find_generic(
            {"_id": ObjectId(backtest_id)},
            self.collection,
        )
        return results[0] if results else None

    def find_all(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """Find all backtests with pagination.

        Args:
            page: Page number (1-based)
            page_size: Items per page

        Returns:
            Tuple of (list of backtests, total count)
        """
        coll = self.db._get_collection(self.collection)
        total = coll.count_documents({})
        skip = (page - 1) * page_size
        results = list(
            coll.find()
            .sort("_id", DESCENDING)
            .skip(skip)
            .limit(page_size)
        )
        return results, total

    def delete(self, backtest_id: str) -> bool:
        """Delete backtest.

        Args:
            backtest_id: Backtest ID

        Returns:
            True if deleted
        """
        return self.db.delete_generic(
            {"_id": ObjectId(backtest_id)},
            self.collection
        ) > 0
