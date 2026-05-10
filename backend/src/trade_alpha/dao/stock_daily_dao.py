"""Stock daily data DAO module."""

from typing import Any
from pymongo import ASCENDING
from trade_alpha.dao.mongodb import MongoDB


class StockDailyDAO:
    """DAO for stock daily collection."""

    def __init__(self, db: MongoDB | None = None):
        self.db = db or MongoDB()
        self.collection = "stock_daily"
        self._ensure_index()

    def _ensure_index(self) -> None:
        self.db.create_index(
            self.collection,
            [("ts_code", ASCENDING), ("trade_date", ASCENDING)],
            unique=True,
        )

    def insert_many(self, records: list[dict[str, Any]]) -> int:
        """Insert stock daily data records.

        Args:
            records: List of stock daily data records

        Returns:
            Number of records upserted/modified
        """
        return self.db.insert_many_generic(
            records,
            self.collection,
            lambda r: {"ts_code": r.get("ts_code"), "trade_date": r.get("trade_date")},
        )

    def find_by_ts_code(self, ts_code: str) -> list[dict[str, Any]]:
        """Find all records for a stock code.

        Args:
            ts_code: Stock code

        Returns:
            List of records sorted by trade_date
        """
        return self.db.find_generic(
            {"ts_code": ts_code},
            self.collection,
            sort_spec=[("trade_date", ASCENDING)],
        )

    def delete_by_ts_code(self, ts_code: str) -> int:
        """Delete all records for a stock code.

        Args:
            ts_code: Stock code

        Returns:
            Number of records deleted
        """
        return self.db.delete_generic({"ts_code": ts_code}, self.collection)

    def get_downloaded_summary(self) -> list[dict[str, Any]]:
        """Get summary of downloaded stocks.

        Returns:
            List of {ts_code, count, latest_date}
        """
        pipeline = [
            {"$group": {
                "_id": "$ts_code",
                "count": {"$sum": 1},
                "latest_date": {"$max": "$trade_date"}
            }},
            {"$project": {
                "ts_code": "$_id",
                "count": 1,
                "latest_date": 1,
                "_id": 0
            }}
        ]
        return self.db.aggregate_generic(pipeline, self.collection)


DailyDAO = StockDailyDAO
