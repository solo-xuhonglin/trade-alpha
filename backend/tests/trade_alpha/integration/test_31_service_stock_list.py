"""Integration tests for stock list service."""

import pytest
from trade_alpha.data.service import fetch_and_store_stock_list
from trade_alpha.dao import StockList


@pytest.mark.integration
@pytest.mark.order(31)
class TestServiceStockList:
    """Integration tests for stock list service."""

    @pytest.mark.asyncio
    async def test_update_stock_list(self, setup_db):
        """Test updating stock list from Tushare."""
        count = await fetch_and_store_stock_list()

        assert count > 0

        stocks = await StockList.find_all().to_list()
        assert len(stocks) > 0

        for stock in stocks[:5]:
            assert hasattr(stock, 'ts_code')
            assert hasattr(stock, 'name')
            assert hasattr(stock, 'market')
            assert stock.market in ["主板", "创业板", "科创板", "北交所"]
