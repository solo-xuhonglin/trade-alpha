"""Integration tests for indicators — data lifecycle Step 2: calculate indicators and activate."""

import pytest
from trade_alpha.indicators import calculate_all_indicators
from trade_alpha.dao import StockDaily, StockList
from trade_alpha.test_config import TEST_STOCK


@pytest.mark.integration
@pytest.mark.order(25)
class TestIndicatorsIntegration:
    """Step 2: Calculate indicators and set sync_status = active."""

    @pytest.mark.asyncio
    async def test_calculate_all_indicators_and_activate(self, setup_db):
        """Calculate all indicators, verify they're stored, set active."""
        ts_code = TEST_STOCK

        # Verify daily data exists
        records = await StockDaily.find(StockDaily.ts_code == ts_code).to_list()
        assert len(records) > 0, "No daily data found — test_20 must run first"

        # Calculate all indicators
        counts = await calculate_all_indicators(ts_code)

        assert counts["ma"] > 0
        assert counts["macd"] > 0
        assert counts["custom"] > 0

        # Verify MA indicators
        records = await StockDaily.find(StockDaily.ts_code == ts_code).to_list()
        records_with_ma = [r for r in records if r.ma_5 is not None]
        assert len(records_with_ma) > 0, "No records with ma_5 populated"
        assert any(r.ma_10 is not None for r in records)
        assert any(r.ma_20 is not None for r in records)
        assert any(r.ma_60 is not None for r in records)

        # Verify MACD indicators
        records_with_macd = [r for r in records if r.macd is not None]
        assert len(records_with_macd) > 0, "No records with macd populated"
        assert any(r.macd_signal is not None for r in records)
        assert any(r.macd_hist is not None for r in records)

        # Verify custom indicators
        assert any(r.pct_chg is not None for r in records)
        assert any(r.bias_5 is not None for r in records)
        assert any(r.kdj_k is not None for r in records)
        assert any(r.boll_middle is not None for r in records)

        # Set sync_status = active (data fully restored)
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        stock.sync_status = "active"
        await stock.save()

        # Verify final state
        stock = await StockList.find_one(StockList.ts_code == ts_code)
        assert stock.sync_status == "active"
