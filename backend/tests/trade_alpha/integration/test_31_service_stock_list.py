"""Integration tests for stock list service — read-only verification."""

import pytest
from trade_alpha.dao import StockList


@pytest.mark.integration
@pytest.mark.order(31)
class TestServiceStockList:
    """Read-only stock list verification — data lifecycle handled by test_20 + test_25."""

    @pytest.mark.asyncio
    async def test_stock_list_has_records(self, setup_db):
        """Verify stock list has records (created by ensure_test_stock fixture)."""
        stocks = await StockList.find_all().to_list()
        assert len(stocks) > 0

    @pytest.mark.asyncio
    async def test_stock_list_records_have_required_fields(self, setup_db):
        """Verify stock list records have the required fields."""
        stocks = await StockList.find_all().to_list()
        assert len(stocks) > 0

        for stock in stocks[:5]:
            assert hasattr(stock, 'ts_code')
            assert hasattr(stock, 'name')
            assert hasattr(stock, 'market')
            assert stock.market in ["主板", "创业板", "科创板", "北交所"]
