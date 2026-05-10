"""Integration tests for Tushare API connectivity."""

import pytest
from trade_alpha.data.fetcher import fetch_stock_list, fetch_daily_basic, fetch_stock_data


@pytest.mark.integration
@pytest.mark.order(1)
class TestTushareAPI:
    """Integration tests for Tushare API connectivity."""

    def test_fetch_stock_list(self):
        """Test fetching stock list from Tushare."""
        df = fetch_stock_list()

        assert df is not None
        assert not df.empty
        assert "ts_code" in df.columns
        assert "name" in df.columns
        assert "market" in df.columns
        assert df["ts_code"].str.endswith((".SH", ".SZ", ".BJ")).all()

    def test_fetch_daily_basic(self):
        """Test fetching daily basic data from Tushare."""
        df = fetch_daily_basic()

        assert df is not None
        assert not df.empty
        assert "ts_code" in df.columns
        assert "total_mv" in df.columns

    def test_fetch_stock_data(self):
        """Test fetching stock daily data from Tushare."""
        df = fetch_stock_data("000001.SZ", "20240101", "20240131")

        assert df is not None
        assert not df.empty
        assert "ts_code" in df.columns
        assert "trade_date" in df.columns
        assert "open" in df.columns
        assert "close" in df.columns
