"""MongoDB storage module."""

from typing import Any
from pymongo import MongoClient, ASCENDING
from pymongo.operations import UpdateOne
from pymongo.errors import BulkWriteError
from config import load_config


class Storage:
    """MongoDB storage handler."""

    def __init__(self, uri: str | None = None, db_name: str | None = None):
        """Initialize storage with MongoDB connection.

        Args:
            uri: MongoDB connection URI
            db_name: Database name
        """
        config = load_config()
        self.uri = uri or config.mongodb_uri
        self.db_name = db_name or config.mongodb_db
        self._client: MongoClient | None = None

    def _get_collection(self, name: str = "daily"):
        """Get MongoDB collection.

        Args:
            name: Collection name

        Returns:
            MongoDB collection
        """
        if self._client is None:
            self._client = MongoClient(self.uri)
        return self._client[self.db_name][name]

    def insert_many(self, records: list[dict[str, Any]], collection: str = "daily") -> int:
        """Insert many records with upsert.

        Args:
            records: List of records to insert
            collection: Collection name

        Returns:
            Number of records inserted/updated
        """
        coll = self._get_collection(collection)
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

    def ensure_index(self, collection: str = "daily") -> None:
        """Ensure compound index on ts_code and trade_date.

        Args:
            collection: Collection name
        """
        coll = self._get_collection(collection)
        coll.create_index([("ts_code", ASCENDING), ("trade_date", ASCENDING)], unique=True)

    def close(self) -> None:
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
            self._client = None
