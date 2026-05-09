"""Integration tests for dao.mongodb module with real environment."""

import pytest
from trade_alpha.data import fetch_and_store
from trade_alpha.dao import MongoDB


class TestMongoDBIntegration:
    """Integration tests with real MongoDB."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.storage = MongoDB()
        self.ts_code = "002594.SZ"
        self.start_date = "20240101"
        self.end_date = "20240131"

        yield

        self.storage.close()

    def cleanup(self):
        coll = self.storage._get_collection()
        coll.delete_many({"ts_code": self.ts_code})

    def count_stored_records(self):
        coll = self.storage._get_collection()
        return coll.count_documents({"ts_code": self.ts_code})

    @pytest.mark.order(1)
    @pytest.mark.integration
    def test_storage_operations(self):
        """Test storage operations: cleanup -> fetch -> store -> verify."""
        self.cleanup()

        assert self.count_stored_records() == 0

        count = fetch_and_store(self.ts_code, self.start_date, self.end_date)

        assert count > 0

        stored_count = self.count_stored_records()
        assert stored_count == count
