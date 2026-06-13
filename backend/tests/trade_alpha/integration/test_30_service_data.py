"""Integration tests for data service — read-only verification."""

import pytest
from trade_alpha.dao import StockDaily
from trade_alpha.test_config import TEST_STOCK

TS_CODE = TEST_STOCK


@pytest.mark.integration
@pytest.mark.order(30)
class TestServiceData:
    """Read-only data service tests — data lifecycle handled by test_20 + test_25."""

    @pytest.mark.asyncio
    async def test_verify_stock_daily_exists(self, setup_db):
        """Verify BYD daily data exists (created by lifecycle tests)."""
        found = await StockDaily.find(StockDaily.ts_code == TS_CODE).to_list()
        assert len(found) > 0, "BYD daily data not found — lifecycle tests (test_20/25) must run first"

    @pytest.mark.asyncio
    async def test_ensure_default_data(self, setup_db):
        """Ensure default stock data exists (no-op if data already present)."""
        existing = await StockDaily.find(StockDaily.ts_code == TS_CODE).to_list()

        if not existing:
            from trade_alpha.data.service import fetch_and_store_stock_daily
            from trade_alpha.indicators.service import calculate_all_indicators
            from trade_alpha.scheduler.stock_data_init_job import get_data_period

            start_date, end_date = get_data_period()
            await fetch_and_store_stock_daily(TS_CODE, start_date, end_date)
            await calculate_all_indicators(TS_CODE)
