"""Integration tests for db.storage module with real environment."""

import pytest
from trade_alpha.data.service import fetch_and_store
from trade_alpha.db.storage import Storage


class TestStorageIntegration:
    """Integration tests with real MongoDB."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.storage = Storage()
        self.ts_code = "002594.SZ"
        self.start_date = "20240101"
        self.end_date = "20240131"

        yield

        self.storage.close()

    def cleanup_data(self):
        coll = self.storage._get_collection()
        coll.delete_many({"ts_code": self.ts_code})

    def count_stored_records(self):
        coll = self.storage._get_collection()
        return coll.count_documents({"ts_code": self.ts_code})

    @pytest.mark.integration
    def test_fetch_and_store_flow(self):
        """Test complete flow: cleanup -> fetch -> store -> verify -> cleanup."""
        self.cleanup_data()

        assert self.count_stored_records() == 0

        count = fetch_and_store(self.ts_code, self.start_date, self.end_date)

        assert count > 0

        stored_count = self.count_stored_records()
        assert stored_count == count

        self.cleanup_data()
