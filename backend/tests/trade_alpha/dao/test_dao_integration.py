"""Integration tests for dao module with Beanie models."""

import pytest
from trade_alpha.dao.mongodb import get_database


@pytest.mark.integration
@pytest.mark.order(1)
class TestDAOIntegration:
    """Integration tests for Beanie document CRUD using dedicated test collection."""

    COLLECTION = "test_dao_items"

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Setup and teardown for each test."""
        db = await get_database()
        self.coll = db[self.COLLECTION]

        await self.coll.delete_many({})

        yield

        await self.coll.drop()

    @pytest.mark.asyncio
    async def test_insert_and_find(self, setup_db):
        """Test insert many and find with sorting."""
        await self.coll.insert_many([
            {"key": "a", "value": 100},
            {"key": "b", "value": 200},
        ])

        cursor = self.coll.find({"key": {"$gte": "a"}}).sort("key", 1)
        found = await cursor.to_list(length=None)
        assert len(found) == 2
        assert found[0]["value"] == 100
        assert found[1]["value"] == 200

    @pytest.mark.asyncio
    async def test_update(self, setup_db):
        """Test insert -> update -> verify."""
        await self.coll.insert_one({"key": "x", "value": 100})

        result = await self.coll.update_one({"key": "x"}, {"$set": {"value": 999}})
        assert result.modified_count == 1

        found = await self.coll.find_one({"key": "x"})
        assert found is not None
        assert found["value"] == 999

    @pytest.mark.asyncio
    async def test_find_one(self, setup_db):
        """Test find_one by unique key."""
        await self.coll.insert_one({"key": "unique", "value": 42})

        found = await self.coll.find_one({"key": "unique"})
        assert found is not None
        assert found["value"] == 42

    @pytest.mark.asyncio
    async def test_delete(self, setup_db):
        """Test insert and delete."""
        await self.coll.insert_one({"key": "del_me", "value": 1})

        result = await self.coll.delete_one({"key": "del_me"})
        assert result.deleted_count == 1

        found = await self.coll.find_one({"key": "del_me"})
        assert found is None
