"""Signal DAO module."""

from typing import Any, Optional
from pymongo import DESCENDING
from trade_alpha.dao.mongodb import MongoDB


class SignalDAO:
    """DAO for signals collection."""

    def __init__(self, db: MongoDB | None = None):
        self.db = db or MongoDB()
        self.collection = "signals"

    def insert(self, doc: dict[str, Any]) -> str:
        """Insert signal document.

        Args:
            doc: Signal document

        Returns:
            Inserted ID as string
        """
        coll = self.db._get_collection(self.collection)
        result = coll.insert_one(doc)
        return str(result.inserted_id)

    def insert_many_generic(
        self,
        records: list[dict[str, Any]],
    ) -> int:
        """Insert signals with upsert.

        Args:
            records: List of signal records

        Returns:
            Number of records upserted/modified
        """
        return self.db.insert_many_generic(
            records,
            self.collection,
            lambda r: {"ts_code": r.get("ts_code"), "trade_date": r.get("trade_date")},
        )

    def find_latest_by_ts_code(self, ts_code: str) -> Optional[dict[str, Any]]:
        """Find latest signal for a stock.

        Args:
            ts_code: Stock code

        Returns:
            Latest signal document or None
        """
        coll = self.db._get_collection(self.collection)
        results = list(
            coll.find({"ts_code": ts_code})
            .sort("trade_date", DESCENDING)
            .limit(1)
        )
        return results[0] if results else None

    def delete_by_ts_code(self, ts_code: str) -> int:
        """Delete all signals for a stock.

        Args:
            ts_code: Stock code

        Returns:
            Number of signals deleted
        """
        return self.db.delete_generic(
            {"ts_code": ts_code},
            self.collection
        )
