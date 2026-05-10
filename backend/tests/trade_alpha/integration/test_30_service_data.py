"""Integration tests for data service."""

import pytest
from trade_alpha.data import fetch_and_store_stock_daily
from trade_alpha.dao import MongoDB, StockDailyDAO


@pytest.mark.integration
@pytest.mark.order(30)
class TestServiceData:
    """Integration tests for data service."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.dao = MongoDB()
        self.ts_code = "002594.SZ"
        self.backup_ts_code = "601398.SH"

        yield

        self.dao.close()

    def test_fetch_and_store_stock_daily(self):
        """Test complete flow: fetch -> store -> verify."""
        coll = self.dao._get_collection("stock_daily")
        coll.delete_many({"ts_code": self.backup_ts_code})

        count = fetch_and_store_stock_daily(self.backup_ts_code, "20240101", "20240131")

        assert count > 0
        assert coll.count_documents({"ts_code": self.backup_ts_code}) == count

        coll.delete_many({"ts_code": self.backup_ts_code})

    def test_ensure_default_data(self):
        """Ensure default stock data exists for Layer 4 tests."""
        dao = StockDailyDAO()
        existing = dao.find_by_ts_code(self.ts_code)

        if not existing:
            fetch_and_store_stock_daily(self.ts_code, "20230101", "20231231")
