"""Integration tests for dao.mongodb module with real environment."""

import pytest
from trade_alpha.dao import MongoDB


class TestDAOIntegration:
    """Integration tests with real MongoDB."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.dao = MongoDB()
        self.ts_code = "002594.SZ"
        self.collection = "test_records"

        yield

        self.dao._get_collection(self.collection).delete_many({"ts_code": self.ts_code})
        self.dao.close()

    def count_records(self):
        return self.dao._get_collection(self.collection).count_documents({"ts_code": self.ts_code})

    @pytest.mark.order(1)
    @pytest.mark.integration
    def test_insert_and_find(self):
        """Test basic MongoDB operations: insert -> find -> verify."""
        records = [
            {"ts_code": self.ts_code, "trade_date": "20240101", "close": 100.0},
            {"ts_code": self.ts_code, "trade_date": "20240102", "close": 101.0},
        ]

        count = self.dao.insert_many(records, collection=self.collection)
        assert count == 2

        found = self.dao.find_by_ts_code(self.ts_code, collection=self.collection)
        assert len(found) == 2
        assert found[0]["close"] == 100.0
        assert found[1]["close"] == 101.0

    @pytest.mark.order(2)
    @pytest.mark.integration
    def test_update(self):
        """Test update operations: insert -> update -> verify."""
        records = [
            {"ts_code": self.ts_code, "trade_date": "20240101", "close": 100.0, "vol": 1000},
        ]
        self.dao.insert_many(records, collection=self.collection)

        updated_records = [
            {"ts_code": self.ts_code, "trade_date": "20240101", "close": 105.0, "vol": 1500},
        ]
        count = self.dao.update_many(updated_records, collection=self.collection)
        assert count >= 1

        found = self.dao.find_by_ts_code(self.ts_code, collection=self.collection)
        assert found[0]["close"] == 105.0
        assert found[0]["vol"] == 1500
