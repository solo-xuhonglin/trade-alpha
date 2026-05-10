"""Integration tests for data service."""

import pytest
from trade_alpha.data.service import fetch_and_store_stock_daily
from trade_alpha.dao import StockDaily
from trade_alpha.indicators.service import calculate_and_store_ma, calculate_and_store_macd


@pytest.mark.integration
@pytest.mark.order(30)
class TestServiceData:
    """Integration tests for data service."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Setup and teardown for each test."""
        self.ts_code = "002594.SZ"
        self.backup_ts_code = "601398.SH"

        yield

        await StockDaily.find(StockDaily.ts_code == self.backup_ts_code).delete()

    @pytest.mark.asyncio
    async def test_fetch_and_store_stock_daily(self, setup_db):
        """Test complete flow: fetch -> store -> verify."""
        await StockDaily.find(StockDaily.ts_code == self.backup_ts_code).delete()

        count = await fetch_and_store_stock_daily(self.backup_ts_code, "20240101", "20240131")

        assert count > 0
        found = await StockDaily.find(StockDaily.ts_code == self.backup_ts_code).to_list()
        assert len(found) >= count

        await StockDaily.find(StockDaily.ts_code == self.backup_ts_code).delete()

    @pytest.mark.asyncio
    async def test_ensure_default_data(self, setup_db):
        """Ensure default stock data exists for Layer 4 tests."""
        existing = await StockDaily.find(StockDaily.ts_code == self.ts_code).to_list()

        if not existing:
            await fetch_and_store_stock_daily(self.ts_code, "20230101", "20231231")
        
        # Calculate indicators for training
        await calculate_and_store_ma(self.ts_code)
        await calculate_and_store_macd(self.ts_code)
