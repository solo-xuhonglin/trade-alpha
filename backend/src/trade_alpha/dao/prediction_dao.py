"""Prediction DAO module."""

from typing import Any, Optional
from pymongo import DESCENDING
from trade_alpha.dao.mongodb import MongoDB


class PredictionDAO:
    """DAO for predictions collection."""

    def __init__(self, db: MongoDB | None = None):
        self.db = db or MongoDB()
        self.collection = "predictions"

    def insert(self, doc: dict[str, Any]) -> str:
        """Insert prediction document.

        Args:
            doc: Prediction document

        Returns:
            Inserted ID as string
        """
        coll = self.db._get_collection(self.collection)
        result = coll.insert_one(doc)
        return str(result.inserted_id)

    def insert_many(self, docs: list[dict[str, Any]]) -> int:
        """Insert multiple prediction documents.

        Args:
            docs: List of prediction documents

        Returns:
            Number of documents inserted
        """
        if not docs:
            return 0
        coll = self.db._get_collection(self.collection)
        result = coll.insert_many(docs)
        return len(result.inserted_ids)

    def find_latest_by_ts_code(self, ts_code: str) -> Optional[dict[str, Any]]:
        """Find latest prediction for a stock.

        Args:
            ts_code: Stock code

        Returns:
            Latest prediction document or None
        """
        coll = self.db._get_collection(self.collection)
        results = list(
            coll.find({"ts_code": ts_code})
            .sort("trade_date", DESCENDING)
            .limit(1)
        )
        return results[0] if results else None

    def find_by_ts_code(
        self,
        ts_code: str,
        limit: int = 1,
    ) -> list[dict[str, Any]]:
        """Find predictions for a stock.

        Args:
            ts_code: Stock code
            limit: Maximum number of results

        Returns:
            List of prediction documents
        """
        coll = self.db._get_collection(self.collection)
        return list(
            coll.find({"ts_code": ts_code})
            .sort("trade_date", DESCENDING)
            .limit(limit)
        )

    def delete_by_ts_code(self, ts_code: str) -> int:
        """Delete all predictions for a stock.

        Args:
            ts_code: Stock code

        Returns:
            Number of predictions deleted
        """
        return self.db.delete_generic(
            {"ts_code": ts_code},
            self.collection
        )
