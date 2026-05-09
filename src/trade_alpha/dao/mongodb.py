"""MongoDB DAO module."""

from typing import Any
from pymongo import MongoClient, ASCENDING
from pymongo.operations import UpdateOne
from pymongo.errors import BulkWriteError
from trade_alpha.config import load_config


class MongoDB:
    """MongoDB DAO handler."""

    def __init__(self, uri: str | None = None, db_name: str | None = None):
        config = load_config()
        self.uri = uri or config.mongodb_uri
        self.db_name = db_name or config.mongodb_db
        self._client: MongoClient | None = None

    def _get_collection(self, name: str = "daily"):
        if self._client is None:
            self._client = MongoClient(self.uri)
        return self._client[self.db_name][name]

    def insert_many(self, records: list[dict[str, Any]], collection: str = "daily") -> int:
        coll = self._get_collection(collection)
        self._ensure_index(collection)
        operations = []
        for record in records:
            ts_code = record.get("ts_code")
            trade_date = record.get("trade_date")
            if ts_code and trade_date:
                operations.append(
                    UpdateOne(
                        {"ts_code": ts_code, "trade_date": trade_date},
                        {"$set": record},
                        upsert=True
                    )
                )

        if not operations:
            return 0

        try:
            result = coll.bulk_write(operations, ordered=False)
            return result.upserted_count + result.modified_count
        except BulkWriteError as e:
            return e.details.get("nUpserted", 0) + e.details.get("nModified", 0)

    def find_by_ts_code(self, ts_code: str, collection: str = "daily") -> list[dict[str, Any]]:
        """Find all records for a stock code.

        Args:
            ts_code: Stock code
            collection: Collection name

        Returns:
            List of records sorted by trade_date
        """
        coll = self._get_collection(collection)
        cursor = coll.find({"ts_code": ts_code}, {"_id": 0}).sort("trade_date", ASCENDING)
        return list(cursor)

    def update_many(self, records: list[dict[str, Any]], collection: str = "daily") -> int:
        """Update records by ts_code and trade_date.

        Args:
            records: List of records to update
            collection: Collection name

        Returns:
            Number of records updated
        """
        return self.insert_many(records, collection)

    def _ensure_index(self, collection: str = "daily") -> None:
        coll = self._get_collection(collection)
        coll.create_index([("ts_code", ASCENDING), ("trade_date", ASCENDING)], unique=True)

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
