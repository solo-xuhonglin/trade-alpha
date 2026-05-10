"""Integration tests for stock list service."""

import pytest
from trade_alpha.data import update_stock_list
from trade_alpha.dao import StockListDAO


@pytest.mark.integration
@pytest.mark.order(31)
class TestServiceStockList:
    """Integration tests for stock list service."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.dao = StockListDAO()

        yield

        self.dao.db.close()

    def test_update_stock_list(self):
        """Test updating stock list from Tushare."""
        count = update_stock_list()

        assert count > 0

        stocks = self.dao.list_stocks()
        assert len(stocks) > 0

        for stock in stocks[:5]:
            assert "ts_code" in stock
            assert "name" in stock
            assert "market" in stock
            assert stock["market"] in ["主板", "创业板", "科创板", "北交所"]
