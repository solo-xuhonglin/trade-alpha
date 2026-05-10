"""Integration tests for StockListDAO business methods."""

import pytest
from trade_alpha.dao import StockListDAO


@pytest.mark.integration
@pytest.mark.order(21)
class TestDAOStockList:
    """Integration tests for StockListDAO business methods."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.dao = StockListDAO()
        self.ts_code = "002594.SZ"
        self.backup_ts_code = "601398.SH"

        yield

        self.dao.db._get_collection("stock_list").delete_many({"ts_code": self.ts_code})
        self.dao.db._get_collection("stock_list").delete_many({"ts_code": self.backup_ts_code})
        self.dao.db.close()

    def test_insert_and_list_stocks(self):
        """Test insert and list operations."""
        records = [
            {
                "ts_code": self.ts_code,
                "name": "比亚迪",
                "industry": "汽车",
                "list_date": "20110602",
                "market": "主板",
                "total_mv": 1000000.0,
                "pe": 10.0,
                "pb": 1.0,
            }
        ]

        count = self.dao.insert_stock_list(records)
        assert count == 1

        stocks = self.dao.list_stocks()
        assert isinstance(stocks, list)

        found = next((s for s in stocks if s["ts_code"] == self.ts_code), None)
        assert found is not None
        assert found["name"] == "比亚迪"

    def test_list_stocks_sorted_by_mv(self):
        """Test that stocks are sorted by total_mv descending."""
        test_stocks = [
            {"ts_code": self.ts_code, "name": "比亚迪", "total_mv": 100000.0},
            {"ts_code": self.backup_ts_code, "name": "工商银行", "total_mv": 10000000.0},
        ]

        for stock in test_stocks:
            self.dao.insert_stock_list([stock])

        stocks = self.dao.list_stocks()

        large_idx = next(i for i, s in enumerate(stocks) if s["ts_code"] == self.backup_ts_code)
        small_idx = next(i for i, s in enumerate(stocks) if s["ts_code"] == self.ts_code)

        assert large_idx < small_idx

    def test_count_stocks(self):
        """Test count stocks."""
        count = self.dao.count_stocks()
        assert count >= 0
