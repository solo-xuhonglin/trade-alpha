"""Integration tests for StockList Beanie model."""

import pytest
from trade_alpha.dao import StockList
from trade_alpha.test_config import TEST_STOCK


@pytest.mark.integration
@pytest.mark.order(21)
class TestStockList:
    """Integration tests for StockList Beanie model."""

    @pytest.mark.asyncio
    async def test_query_test_stock(self, ensure_test_stock):
        """Test that test stock exists and has correct data."""
        ts_code = ensure_test_stock

        stock = await StockList.find_one(StockList.ts_code == ts_code)
        assert stock is not None
        assert stock.name == "比亚迪"

    @pytest.mark.asyncio
    async def test_list_stocks_sorted_by_mv(self, setup_db):
        """Test that stocks are sorted by total_mv descending using real data."""
        stocks = await StockList.find_all().sort(-StockList.total_mv).to_list()

        assert len(stocks) > 0

        # Only verify real data entries that have total_mv
        stocks_with_mv = [s for s in stocks if s.total_mv is not None]
        assert len(stocks_with_mv) > 0

        for i in range(len(stocks_with_mv) - 1):
            assert stocks_with_mv[i].total_mv >= stocks_with_mv[i + 1].total_mv, \
                f"Sort order broken at index {i}: {stocks_with_mv[i].ts_code} ({stocks_with_mv[i].total_mv}) > {stocks_with_mv[i + 1].ts_code} ({stocks_with_mv[i + 1].total_mv})"

    @pytest.mark.asyncio
    async def test_count_stocks(self, setup_db):
        """Test count stocks."""
        count = await StockList.count()
        assert count > 0
