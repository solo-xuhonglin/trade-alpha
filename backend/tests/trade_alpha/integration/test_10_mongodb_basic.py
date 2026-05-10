"""Integration tests for MongoDB basic operations."""

import pytest
from trade_alpha.dao.mongodb import MongoDB


@pytest.mark.integration
@pytest.mark.order(10)
class TestMongoDBBasic:
    """Integration tests for MongoDB basic operations using test collection."""

    COLLECTION = "test_collection"

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.db = MongoDB()
        self.coll = self.db._get_collection(self.COLLECTION)

        yield

        self.coll.drop()
        self.db.close()

    def test_insert_many_generic(self):
        """Test generic insert/update operation."""
        records = [
            {"id": 1, "name": "test1", "value": 100},
            {"id": 2, "name": "test2", "value": 200},
        ]

        count = self.db.insert_many_generic(
            records,
            self.COLLECTION,
            lambda r: {"id": r["id"]},
            [("id", 1)],
        )

        assert count == 2
        assert self.coll.count_documents({}) == 2

    def test_find_generic(self):
        """Test generic find operation."""
        self.coll.insert_many([
            {"id": 1, "name": "test1", "value": 100},
            {"id": 2, "name": "test2", "value": 200},
            {"id": 3, "name": "test3", "value": 300},
        ])

        results = self.db.find_generic(
            {"value": {"$gte": 200}},
            self.COLLECTION,
            sort_spec=[("value", -1)],
        )

        assert len(results) == 2
        assert results[0]["id"] == 3

    def test_find_generic_with_pagination(self):
        """Test generic find with pagination."""
        self.coll.insert_many([
            {"id": i, "name": f"test{i}"} for i in range(1, 11)
        ])

        page1 = self.db.find_generic({}, self.COLLECTION, sort_spec=[("id", 1)], skip=0, limit=5)
        page2 = self.db.find_generic({}, self.COLLECTION, sort_spec=[("id", 1)], skip=5, limit=5)

        assert len(page1) == 5
        assert len(page2) == 5
        assert page1[0]["id"] == 1
        assert page2[0]["id"] == 6

    def test_delete_generic(self):
        """Test generic delete operation."""
        self.coll.insert_many([
            {"id": 1, "name": "test1"},
            {"id": 2, "name": "test2"},
        ])

        deleted = self.db.delete_generic({"id": 1}, self.COLLECTION)

        assert deleted == 1
        assert self.coll.count_documents({}) == 1

    def test_aggregate_generic(self):
        """Test generic aggregate operation."""
        self.coll.insert_many([
            {"category": "A", "value": 100},
            {"category": "A", "value": 200},
            {"category": "B", "value": 300},
        ])

        pipeline = [
            {"$group": {"_id": "$category", "total": {"$sum": "$value"}}},
            {"$sort": {"total": -1}},
        ]

        results = self.db.aggregate_generic(pipeline, self.COLLECTION)

        assert len(results) == 2
        assert results[0]["total"] == 300

    def test_create_index(self):
        """Test index creation."""
        self.db.create_index(self.COLLECTION, [("name", 1)], unique=True)

        indexes = list(self.coll.list_indexes())
        index_names = [idx["name"] for idx in indexes]

        assert "name_1" in index_names
