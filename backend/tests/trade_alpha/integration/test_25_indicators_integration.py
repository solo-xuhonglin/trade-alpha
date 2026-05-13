"""Integration tests for indicators module with real environment."""

import pytest
from trade_alpha.indicators import calculate_all_indicators
from trade_alpha.dao import StockDaily


@pytest.mark.integration
@pytest.mark.order(25)
class TestIndicatorsIntegration:
    """Integration tests with real MongoDB."""

    @pytest.mark.asyncio
    async def test_calculate_all_indicators(self, test_stock):
        """Test calculate all indicators using unified interface."""
        ts_code = test_stock
        
        # Verify data exists
        records = await StockDaily.find(StockDaily.ts_code == ts_code).to_list()
        assert len(records) > 0
        
        # Call unified indicator calculation
        counts = await calculate_all_indicators(ts_code)
        
        assert counts["ma"] > 0
        assert counts["macd"] > 0
        assert counts["custom"] > 0
        
        # Verify indicators were stored
        records = await StockDaily.find(StockDaily.ts_code == ts_code).to_list()
        assert len(records) > 0
        
        # Check MA indicators
        records_with_ma = [r for r in records if r.ma_5 is not None]
        assert len(records_with_ma) > 0, "No records with ma_5 populated"
        assert any(r.ma_10 is not None for r in records)
        assert any(r.ma_20 is not None for r in records)
        assert any(r.ma_60 is not None for r in records)
        
        # Check MACD indicators
        records_with_macd = [r for r in records if r.macd is not None]
        assert len(records_with_macd) > 0, "No records with macd populated"
        assert any(r.macd_signal is not None for r in records)
        assert any(r.macd_hist is not None for r in records)
        
        # Check custom indicators
        assert any(r.pct_chg is not None for r in records)
        assert any(r.bias_5 is not None for r in records)
        assert any(r.kdj_k is not None for r in records)
        assert any(r.boll_middle is not None for r in records)
