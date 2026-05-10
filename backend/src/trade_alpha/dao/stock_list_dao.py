"""Stock list DAO module."""

from typing import Any
from datetime import datetime, timezone
from pymongo import ASCENDING, DESCENDING
from trade_alpha.dao.mongodb import MongoDB


class StockListDAO:
    """DAO for stock_list collection."""

    def __init__(self, db: MongoDB | None = None):
        self.db = db or MongoDB()
        self.collection = "stock_list"
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.db.create_index(self.collection, [("ts_code", ASCENDING)], unique=True)
        self.db.create_index(self.collection, [("total_mv", DESCENDING)])

    def insert_stock_list(self, records: list[dict[str, Any]]) -> int:
        """Insert stock list records.

        Args:
            records: List of stock records

        Returns:
            Number of records upserted/modified
        """
        now = datetime.now(timezone.utc)
        for record in records:
            record["updated_at"] = now
        return self.db.insert_many_generic(
            records,
            self.collection,
            lambda r: {"ts_code": r.get("ts_code")},
            [("ts_code", ASCENDING)],
        )

    def list_stocks(self, skip: int = 0, limit: int = 0) -> list[dict[str, Any]]:
        """List stocks sorted by market cap descending.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return (0 = no limit)

        Returns:
            List of stock records
        """
        return self.db.find_generic(
            {},
            self.collection,
            sort_spec=[("total_mv", DESCENDING)],
            skip=skip,
            limit=limit,
        )

    def count_stocks(self) -> int:
        """Count total stocks.

        Returns:
            Total number of stocks
        """
        coll = self.db._get_collection(self.collection)
        return coll.count_documents({})
