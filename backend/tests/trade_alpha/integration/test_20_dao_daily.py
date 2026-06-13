"""Integration tests for data lifecycle — Step 1: fetch daily data."""

import pytest
from trade_alpha.dao import StockDaily, StockList
from trade_alpha.data.service import fetch_and_store_stock_daily
from trade_alpha.scheduler.stock_data_init_job import get_data_period
from trade_alpha.test_config import TEST_STOCK


@pytest.mark.integration
@pytest.mark.order(20)
class TestDataLifecycle:
    """Data lifecycle: pending -> fetch -> indicators -> active.

    Step 1: Delete daily data, set pending, fetch 20 years from Tushare.
    """

    @pytest.fixture(autouse=True)
    async def setup(self, ensure_test_stock):
        """Ensure BYD stock list entry exists."""
        self.ts_code = TEST_STOCK

    @pytest.mark.asyncio
    async def test_delete_and_fetch_stock_daily(self):
        """Step 1: Delete BYD daily data -> set pending -> fetch 20 years."""
        ts_code = self.ts_code

        # Delete existing daily data
        await StockDaily.find(StockDaily.ts_code == ts_code).delete()

        # Set sync_status = pending
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        stock.sync_status = "pending"
        await stock.save()

        # Fetch 20 years of daily data using get_data_period
        start_date, end_date = get_data_period()
        count = await fetch_and_store_stock_daily(ts_code, start_date, end_date)

        assert count > 0, "No new daily records inserted"

        # Verify data exists
        found = await StockDaily.find(StockDaily.ts_code == ts_code).to_list()
        assert len(found) > 0

        # Verify sync_status is still pending
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        assert stock.sync_status == "pending"
