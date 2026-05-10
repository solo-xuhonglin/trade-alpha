"""Integration tests for MongoDB basic operations using Beanie."""

import pytest
from trade_alpha.dao.mongodb import get_database


@pytest.mark.integration
@pytest.mark.order(10)
class TestMongoDBBasic:
    """Integration tests for MongoDB basic operations using test collection."""

    COLLECTION = "test_collection"

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Setup and teardown for each test."""
        db = await get_database()
        self.coll = db[self.COLLECTION]

        yield

        await self.coll.drop()

    @pytest.mark.asyncio
    async def test_insert_many_generic(self, setup_db):
        """Test generic insert/update operation."""
        db = await get_database()
        coll = db[self.COLLECTION]
        
        records = [
            {"id": 1, "name": "test1", "value": 100},
            {"id": 2, "name": "test2", "value": 200},
        ]

        await coll.insert_many(records)

        count = await coll.count_documents({})
        assert count == 2

    @pytest.mark.asyncio
    async def test_find_generic(self, setup_db):
        """Test generic find operation."""
        db = await get_database()
        coll = db[self.COLLECTION]
        
        await coll.insert_many([
            {"id": 1, "name": "test1", "value": 100},
            {"id": 2, "name": "test2", "value": 200},
            {"id": 3, "name": "test3", "value": 300},
        ])

        results = []
        async for doc in coll.find({"value": {"$gte": 200}}).sort("value", -1):
            results.append(doc)

        assert len(results) == 2
        assert results[0]["id"] == 3

    @pytest.mark.asyncio
    async def test_find_generic_with_pagination(self, setup_db):
        """Test generic find with pagination."""
        db = await get_database()
        coll = db[self.COLLECTION]
        
        await coll.insert_many([
            {"id": i, "name": f"test{i}"} for i in range(1, 11)
        ])

        page1 = []
        async for doc in coll.find({}).sort("id", 1).skip(0).limit(5):
            page1.append(doc)
        
        page2 = []
        async for doc in coll.find({}).sort("id", 1).skip(5).limit(5):
            page2.append(doc)

        assert len(page1) == 5
        assert len(page2) == 5
        assert page1[0]["id"] == 1
        assert page2[0]["id"] == 6

    @pytest.mark.asyncio
    async def test_delete_generic(self, setup_db):
        """Test generic delete operation."""
        db = await get_database()
        coll = db[self.COLLECTION]
        
        await coll.insert_many([
            {"id": 1, "name": "test1"},
            {"id": 2, "name": "test2"},
        ])

        result = await coll.delete_one({"id": 1})
        assert result.deleted_count == 1
        count = await coll.count_documents({})
        assert count == 1

    @pytest.mark.asyncio
    async def test_aggregate_generic(self, setup_db):
        """Test generic aggregate operation."""
        db = await get_database()
        coll = db[self.COLLECTION]
        
        await coll.insert_many([
            {"category": "A", "value": 100},
            {"category": "A", "value": 200},
            {"category": "B", "value": 300},
        ])

        pipeline = [
            {"$group": {"_id": "$category", "total": {"$sum": "$value"}}},
            {"$sort": {"total": -1}},
        ]

        results = []
        async for doc in coll.aggregate(pipeline):
            results.append(doc)

        assert len(results) == 2
        assert results[0]["total"] == 300

    @pytest.mark.asyncio
    async def test_create_index(self, setup_db):
        """Test index creation."""
        db = await get_database()
        coll = db[self.COLLECTION]
        
        await coll.create_index([("name", 1)], unique=True)

        indexes = []
        async for idx in coll.list_indexes():
            indexes.append(idx)

        index_names = [idx["name"] for idx in indexes]
        assert "name_1" in index_names
