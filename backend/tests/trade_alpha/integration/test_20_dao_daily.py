"""Integration tests for StockDailyDAO business methods."""

import pytest
from trade_alpha.dao import StockDailyDAO


@pytest.mark.integration
@pytest.mark.order(20)
class TestDAODaily:
    """Integration tests for StockDailyDAO business methods."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.dao = StockDailyDAO()
        self.ts_code = "002594.SZ"

        yield

        self.dao.delete_by_ts_code(self.ts_code)
        self.dao.db.close()

    def test_insert_and_find(self):
        """Test insert and find operations."""
        records = [
            {"ts_code": self.ts_code, "trade_date": "20240101", "open": 10.0, "close": 10.5, "high": 10.8, "low": 9.9, "vol": 1000, "amount": 10000},
            {"ts_code": self.ts_code, "trade_date": "20240102", "open": 10.5, "close": 11.0, "high": 11.2, "low": 10.3, "vol": 1200, "amount": 12000},
        ]

        count = self.dao.insert_many(records)
        assert count == 2

        found = self.dao.find_by_ts_code(self.ts_code)
        assert len(found) >= 2
        dates = [r["trade_date"] for r in found]
        assert "20240101" in dates
        assert "20240102" in dates

    def test_delete_by_ts_code(self):
        """Test delete operation."""
        records = [
            {"ts_code": self.ts_code, "trade_date": "20240101", "open": 10.0, "close": 10.5, "high": 10.8, "low": 9.9, "vol": 1000, "amount": 10000},
        ]
        self.dao.insert_many(records)

        deleted = self.dao.delete_by_ts_code(self.ts_code)
        assert deleted >= 1

        found = self.dao.find_by_ts_code(self.ts_code)
        assert len(found) == 0

    def test_get_downloaded_summary(self):
        """Test get downloaded summary."""
        records = [
            {"ts_code": self.ts_code, "trade_date": "20240101", "open": 10.0, "close": 10.5, "high": 10.8, "low": 9.9, "vol": 1000, "amount": 10000},
            {"ts_code": self.ts_code, "trade_date": "20240102", "open": 10.5, "close": 11.0, "high": 11.2, "low": 10.3, "vol": 1200, "amount": 12000},
        ]
        self.dao.insert_many(records)

        summary = self.dao.get_downloaded_summary()
        assert isinstance(summary, list)

        found = next((s for s in summary if s["ts_code"] == self.ts_code), None)
        assert found is not None
        assert found["count"] == 2
        assert found["latest_date"] == "20240102"
