"""Integration tests for data service."""

import pytest
from trade_alpha.data import fetch_and_store
from trade_alpha.dao import MongoDB


@pytest.mark.integration
@pytest.mark.order(30)
class TestServiceData:
    """Integration tests for data service."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.dao = MongoDB()
        self.ts_code = "002594.SZ"

        yield

        self.dao._get_collection("daily").delete_many({"ts_code": self.ts_code})
        self.dao.close()

    def test_fetch_and_store(self):
        """Test complete flow: fetch -> store -> verify."""
        coll = self.dao._get_collection("daily")
        coll.delete_many({"ts_code": self.ts_code})

        count = fetch_and_store(self.ts_code, "20240101", "20240131")

        assert count > 0
        assert coll.count_documents({"ts_code": self.ts_code}) == count
