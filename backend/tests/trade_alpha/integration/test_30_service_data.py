"""Integration tests for data service."""

import pytest
from trade_alpha.data.service import fetch_and_store_stock_daily
from trade_alpha.dao import StockDaily
from trade_alpha.indicators.service import calculate_and_store_ma, calculate_and_store_macd, calculate_all_indicators

TS_CODE = "002594.SZ"


@pytest.mark.integration
@pytest.mark.order(30)
class TestServiceData:
    """Integration tests for data service."""

    @pytest.mark.asyncio
    async def test_fetch_and_store_stock_daily(self, setup_db):
        """Test complete flow: fetch -> store -> verify."""
        count = await fetch_and_store_stock_daily(TS_CODE, "20240101", "20240131")

        assert count > 0
        found = await StockDaily.find(StockDaily.ts_code == TS_CODE, StockDaily.trade_date >= "20240101", StockDaily.trade_date <= "20240131").to_list()
        assert len(found) >= count

    @pytest.mark.asyncio
    async def test_ensure_default_data(self, setup_db):
        """Ensure default stock data exists for Layer 4 tests."""
        existing = await StockDaily.find(StockDaily.ts_code == TS_CODE).to_list()

        if not existing:
            await fetch_and_store_stock_daily(TS_CODE, "20230101", "20231231")
        
        # Calculate all indicators
        await calculate_all_indicators(TS_CODE)
