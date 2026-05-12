"""Integration tests for indicators module with real environment."""

import pytest
from trade_alpha.indicators import (
    calculate_and_store_ma,
    calculate_and_store_macd,
    calculate_and_store_custom_indicators,
)
from trade_alpha.dao import StockDaily


@pytest.mark.integration
@pytest.mark.order(3)
class TestIndicatorsIntegration:
    """Integration tests with real MongoDB."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Setup and teardown for each test."""
        self.ts_code = "002594.SZ"

        yield

    @pytest.mark.asyncio
    async def test_calculate_indicators(self):
        """Test calculate and store indicators."""
        records = await StockDaily.find(StockDaily.ts_code == self.ts_code).to_list()
        assert len(records) > 0, "No data available, run data integration test first"

        ma_count = await calculate_and_store_ma(self.ts_code)
        assert ma_count > 0

        macd_count = await calculate_and_store_macd(self.ts_code)
        assert macd_count > 0

        custom_count = await calculate_and_store_custom_indicators(self.ts_code)
        assert custom_count > 0

        records = await StockDaily.find(StockDaily.ts_code == self.ts_code).to_list()
        assert len(records) > 0

        records_with_ma = [r for r in records if r.ma_5 is not None]
        assert len(records_with_ma) > 0, "No records with ma_5 populated"

        records_with_macd = [r for r in records if r.macd is not None]
        assert len(records_with_macd) > 0, "No records with macd populated"

        assert any(r.ma_10 is not None for r in records)
        assert any(r.macd_signal is not None for r in records)
        assert any(r.macd_hist is not None for r in records)
