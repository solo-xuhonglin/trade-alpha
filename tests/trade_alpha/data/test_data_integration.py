"""Integration tests for data module with real environment."""

import pytest
from trade_alpha.data import fetch_and_store
from trade_alpha.dao import MongoDB


class TestDataIntegration:
    """Integration tests with real Tushare API and MongoDB."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.storage = MongoDB()
        self.ts_code = "002594.SZ"
        self.start_date = "20240101"
        self.end_date = "20240131"

        yield

        self.storage.close()

    def cleanup(self):
        """Clean up test data from MongoDB."""
        coll = self.storage._get_collection()
        coll.delete_many({"ts_code": self.ts_code})

    def count_stored_records(self):
        """Count stored records for the test stock."""
        coll = self.storage._get_collection()
        return coll.count_documents({"ts_code": self.ts_code})

    @pytest.mark.order(2)
    @pytest.mark.integration
    def test_fetch_and_store(self):
        """Test complete flow: fetch -> store -> verify."""
        assert self.count_stored_records() > 0
