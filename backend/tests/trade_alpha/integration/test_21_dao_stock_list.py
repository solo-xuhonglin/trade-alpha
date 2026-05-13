"""Integration tests for StockList Beanie model."""

import pytest
from trade_alpha.dao import StockList


@pytest.mark.integration
@pytest.mark.order(21)
class TestStockList:
    """Integration tests for StockList Beanie model."""

    @pytest.mark.asyncio
    async def test_query_test_stock(self, test_stock):
        """Test that test stock exists and has correct data."""
        ts_code = test_stock
        
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        assert stock is not None
        assert stock.name == "比亚迪"
        assert stock.sync_status == "active"

    @pytest.mark.asyncio
    async def test_list_stocks_sorted_by_mv(self, setup_db):
        """Test that stocks are sorted by total_mv descending."""
        # First cleanup if exist
        await StockList.find(StockList.ts_code == "000001.SZ").delete()
        await StockList.find(StockList.ts_code == "000002.SZ").delete()
        
        # Insert test stocks
        test_stock1 = StockList(ts_code="000001.SZ", name="平安银行", total_mv=100000.0)
        test_stock2 = StockList(ts_code="000002.SZ", name="万科A", total_mv=10000000.0)
        await test_stock1.insert()
        await test_stock2.insert()

        # Query sorted list
        stocks = await StockList.find_all().sort(-StockList.total_mv).to_list()
        
        # Filter only our test stocks
        test_stocks_only = [s for s in stocks if s.ts_code in ("000001.SZ", "000002.SZ")]
        
        # Verify order
        assert test_stocks_only[0].ts_code == "000002.SZ"
        assert test_stocks_only[1].ts_code == "000001.SZ"
        
        # Cleanup
        await StockList.find(StockList.ts_code == "000001.SZ").delete()
        await StockList.find(StockList.ts_code == "000002.SZ").delete()

    @pytest.mark.asyncio
    async def test_count_stocks(self, setup_db):
        """Test count stocks."""
        count = await StockList.count()
        assert count >= 0
