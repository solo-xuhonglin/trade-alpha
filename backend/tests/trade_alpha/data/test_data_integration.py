"""Integration tests for data module with real environment."""

import pytest
from trade_alpha.data import fetch_and_store, update_stock_list
from trade_alpha.data.fetcher import fetch_stock_list, fetch_daily_basic, fetch_stock_data
from trade_alpha.dao import MongoDB, DailyDAO, StockListDAO


class TestDataIntegration:
    """Integration tests with real Tushare API and MongoDB."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.dao = MongoDB()
        self.ts_code = "002594.SZ"
        self.start_date = "20240101"
        self.end_date = "20240131"

        yield

        self.dao.close()

    def cleanup_daily(self):
        """Clean up test data from MongoDB daily collection."""
        coll = self.dao._get_collection("daily")
        coll.delete_many({"ts_code": self.ts_code})

    def count_stored_records(self):
        """Count stored records for the test stock."""
        coll = self.dao._get_collection("daily")
        return coll.count_documents({"ts_code": self.ts_code})

    @pytest.mark.order(2)
    @pytest.mark.integration
    def test_fetch_and_store(self):
        """Test complete flow: cleanup -> fetch -> store -> verify."""
        self.cleanup_daily()

        assert self.count_stored_records() == 0

        count = fetch_and_store(self.ts_code, self.start_date, self.end_date)

        assert count > 0

        stored_count = self.count_stored_records()
        assert stored_count == count


class TestFetcherIntegration:
    """Integration tests for fetcher module with real Tushare API."""

    @pytest.mark.integration
    def test_fetch_stock_list(self):
        """Test fetching stock list from Tushare."""
        df = fetch_stock_list()

        assert df is not None
        assert not df.empty
        assert "ts_code" in df.columns
        assert "name" in df.columns
        assert "market" in df.columns

        assert len(df) > 0

        assert df["ts_code"].str.endswith((".SH", ".SZ", ".BJ")).all()

    @pytest.mark.integration
    def test_fetch_daily_basic(self):
        """Test fetching daily basic data from Tushare."""
        df = fetch_daily_basic()

        assert df is not None
        assert not df.empty
        assert "ts_code" in df.columns
        assert "total_mv" in df.columns

    @pytest.mark.integration
    def test_fetch_stock_data(self):
        """Test fetching stock daily data from Tushare."""
        df = fetch_stock_data("000001.SZ", "20240101", "20240131")

        assert df is not None
        assert not df.empty
        assert "ts_code" in df.columns
        assert "trade_date" in df.columns
        assert "open" in df.columns
        assert "close" in df.columns


class TestDailyDAOIntegration:
    """Integration tests for DailyDAO with real MongoDB."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.dao = DailyDAO()
        self.ts_code = "002594.SZ"

        yield

        self.dao.db.close()

    def cleanup(self):
        """Clean up test data."""
        self.dao.delete_by_ts_code(self.ts_code)

    @pytest.mark.integration
    def test_insert_and_find(self):
        """Test insert and find operations."""
        self.cleanup()

        records = [
            {"ts_code": self.ts_code, "trade_date": "20240101", "open": 10.0, "close": 10.5, "high": 10.8, "low": 9.9, "vol": 1000, "amount": 10000},
            {"ts_code": self.ts_code, "trade_date": "20240102", "open": 10.5, "close": 11.0, "high": 11.2, "low": 10.3, "vol": 1200, "amount": 12000},
        ]

        count = self.dao.insert_many(records)
        assert count == 2

        found = self.dao.find_by_ts_code(self.ts_code)
        assert len(found) == 2
        assert found[0]["trade_date"] == "20240101"

    @pytest.mark.integration
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

    @pytest.mark.integration
    def test_get_downloaded_summary(self):
        """Test get downloaded summary."""
        self.cleanup()

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

        self.cleanup()


class TestStockListDAOIntegration:
    """Integration tests for StockListDAO with real MongoDB."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.dao = StockListDAO()
        self.test_ts_code = "999999.TEST"

        yield

        self.dao.db._get_collection("stock_list").delete_many({"ts_code": self.test_ts_code})
        self.dao.db.close()

    @pytest.mark.integration
    def test_insert_and_list_stocks(self):
        """Test insert and list operations."""
        records = [
            {
                "ts_code": self.test_ts_code,
                "name": "测试股票",
                "industry": "测试",
                "list_date": "20240101",
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
        assert len(stocks) > 0

        found = next((s for s in stocks if s["ts_code"] == self.test_ts_code), None)
        assert found is not None
        assert found["name"] == "测试股票"
        assert found["market"] == "主板"

    @pytest.mark.integration
    def test_list_stocks_sorted_by_mv(self):
        """Test that stocks are sorted by total_mv descending."""
        test_stocks = [
            {"ts_code": "999998.TEST", "name": "小市值", "total_mv": 100000.0},
            {"ts_code": "999997.TEST", "name": "大市值", "total_mv": 10000000.0},
        ]

        for stock in test_stocks:
            self.dao.insert_stock_list([stock])

        stocks = self.dao.list_stocks()

        large_idx = next(i for i, s in enumerate(stocks) if s["ts_code"] == "999997.TEST")
        small_idx = next(i for i, s in enumerate(stocks) if s["ts_code"] == "999998.TEST")

        assert large_idx < small_idx

        for ts_code in ["999998.TEST", "999997.TEST"]:
            self.dao.db._get_collection("stock_list").delete_many({"ts_code": ts_code})


class TestServiceIntegration:
    """Integration tests for service module with real environment."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.stock_list_dao = StockListDAO()

        yield

        self.stock_list_dao.db._get_collection("stock_list").delete_many({"ts_code": "999999.TEST"})
        self.stock_list_dao.db.close()

    @pytest.mark.integration
    def test_update_stock_list(self):
        """Test updating stock list from Tushare."""
        count = update_stock_list()

        assert count > 0

        stocks = self.stock_list_dao.list_stocks()
        assert len(stocks) > 0

        for stock in stocks[:5]:
            assert "ts_code" in stock
            assert "name" in stock
            assert "market" in stock
            assert stock["market"] in ["主板", "创业板", "科创板", "北交所"]
