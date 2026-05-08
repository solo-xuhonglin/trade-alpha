"""Integration tests with real environment."""

import pytest
from data.fetcher import fetch_stock_data


class TestIntegration:
    """Integration tests with real Tushare API."""

    @pytest.mark.integration
    def test_fetch_real_stock_data(self):
        """Test fetching real stock data from Tushare."""
        result = fetch_stock_data("002594.SZ", "20240101", "20240131")

        assert result is not None
        assert len(result) > 0
        assert result.iloc[0]["ts_code"] == "002594.SZ"
        assert "trade_date" in result.columns
        assert "open" in result.columns
        assert "close" in result.columns

    @pytest.mark.integration
    def test_fetch_real_stock_data_sorted(self):
        """Test that real data is sorted by trade_date."""
        result = fetch_stock_data("002594.SZ", "20240101", "20240110")

        assert result is not None
        dates = result["trade_date"].tolist()
        assert dates == sorted(dates)
