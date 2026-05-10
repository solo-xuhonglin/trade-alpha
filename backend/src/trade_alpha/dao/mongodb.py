"""MongoDB DAO module."""

from typing import Any, Callable
from pymongo import MongoClient, ASCENDING, DESCENDING
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

    def _get_collection(self, name: str):
        if self._client is None:
            self._client = MongoClient(self.uri)
        return self._client[self.db_name][name]

    def insert_many_generic(
        self,
        records: list[dict[str, Any]],
        collection: str,
        filter_builder: Callable[[dict[str, Any]], dict[str, Any]],
        index_spec: list[tuple[str, int]] | None = None,
    ) -> int:
        """Generic bulk insert/update method.

        Args:
            records: List of records to insert/update
            collection: Collection name
            filter_builder: Function to build filter for each record
            index_spec: Index specification to create

        Returns:
            Number of records upserted/modified
        """
        coll = self._get_collection(collection)
        if index_spec:
            coll.create_index(index_spec, unique=True)
        operations = []
        for record in records:
            filter_query = filter_builder(record)
            if filter_query:
                operations.append(
                    UpdateOne(filter_query, {"$set": record}, upsert=True)
                )

        if not operations:
            return 0

        try:
            result = coll.bulk_write(operations, ordered=False)
            return result.upserted_count + result.modified_count
        except BulkWriteError as e:
            return e.details.get("nUpserted", 0) + e.details.get("nModified", 0)

    def find_generic(
        self,
        filter_query: dict[str, Any],
        collection: str,
        sort_spec: list[tuple[str, int]] | None = None,
        projection: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 0,
    ) -> list[dict[str, Any]]:
        """Generic find method.

        Args:
            filter_query: Filter query
            collection: Collection name
            sort_spec: Sort specification
            projection: Projection
            skip: Number of records to skip
            limit: Maximum number of records to return (0 = no limit)

        Returns:
            List of records
        """
        coll = self._get_collection(collection)
        cursor = coll.find(filter_query, projection or {"_id": 0})
        if sort_spec:
            cursor = cursor.sort(sort_spec)
        if skip > 0:
            cursor = cursor.skip(skip)
        if limit > 0:
            cursor = cursor.limit(limit)
        return list(cursor)

    def delete_generic(self, filter_query: dict[str, Any], collection: str) -> int:
        """Generic delete method.

        Args:
            filter_query: Filter query
            collection: Collection name

        Returns:
            Number of records deleted
        """
        coll = self._get_collection(collection)
        result = coll.delete_many(filter_query)
        return result.deleted_count

    def aggregate_generic(
        self,
        pipeline: list[dict[str, Any]],
        collection: str,
    ) -> list[dict[str, Any]]:
        """Generic aggregate method.

        Args:
            pipeline: Aggregation pipeline
            collection: Collection name

        Returns:
            List of aggregation results
        """
        coll = self._get_collection(collection)
        return list(coll.aggregate(pipeline))

    def create_index(self, collection: str, index_spec: list[tuple[str, int]], unique: bool = False) -> None:
        """Create an index.

        Args:
            collection: Collection name
            index_spec: Index specification
            unique: Whether index is unique
        """
        coll = self._get_collection(collection)
        coll.create_index(index_spec, unique=unique)

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
