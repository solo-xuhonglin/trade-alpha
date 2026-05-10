"""Integration tests for StockList Beanie model."""

import pytest
from trade_alpha.dao import StockList


@pytest.mark.integration
@pytest.mark.order(21)
class TestStockList:
    """Integration tests for StockList Beanie model."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Setup and teardown for each test."""
        self.ts_code = "002594.SZ"
        self.backup_ts_code = "601398.SH"

        yield

        await StockList.find(StockList.ts_code == self.ts_code).delete()
        await StockList.find(StockList.ts_code == self.backup_ts_code).delete()

    @pytest.mark.asyncio
    async def test_insert_and_list_stocks(self, setup_db):
        """Test insert and list operations."""
        record = StockList(
            ts_code=self.ts_code,
            name="比亚迪",
            industry="汽车",
            list_date="20110602",
            market="主板",
            total_mv=1000000.0,
            pe=10.0,
            pb=1.0,
        )
        await record.insert()

        stocks = await StockList.find_all().to_list()
        assert isinstance(stocks, list)

        found = next((s for s in stocks if s.ts_code == self.ts_code), None)
        assert found is not None
        assert found.name == "比亚迪"

    @pytest.mark.asyncio
    async def test_list_stocks_sorted_by_mv(self, setup_db):
        """Test that stocks are sorted by total_mv descending."""
        stock1 = StockList(ts_code=self.ts_code, name="比亚迪", total_mv=100000.0)
        stock2 = StockList(ts_code=self.backup_ts_code, name="工商银行", total_mv=10000000.0)
        await stock1.insert()
        await stock2.insert()

        stocks = await StockList.find_all().sort(-StockList.total_mv).to_list()

        large_idx = next(i for i, s in enumerate(stocks) if s.ts_code == self.backup_ts_code)
        small_idx = next(i for i, s in enumerate(stocks) if s.ts_code == self.ts_code)

        assert large_idx < small_idx

    @pytest.mark.asyncio
    async def test_count_stocks(self, setup_db):
        """Test count stocks."""
        count = await StockList.count()
        assert count >= 0
