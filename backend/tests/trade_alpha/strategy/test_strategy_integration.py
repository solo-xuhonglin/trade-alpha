"""Integration tests for strategy module."""

import pytest
from trade_alpha.strategy import generate_signal
from trade_alpha.dao import StockDaily, PredictionResult, SignalResult


@pytest.mark.integration
@pytest.mark.order(55)
class TestStrategyIntegration:
    """Integration tests with real MongoDB."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Setup and teardown for each test."""
        self.ts_code = "002594.SZ"

        yield

        await SignalResult.find(SignalResult.ts_code == self.ts_code).delete()

    @pytest.mark.asyncio
    async def test_generate_signal(self):
        """Test generate signal with existing predictions."""
        records = await StockDaily.find(StockDaily.ts_code == self.ts_code).to_list()
        if not records:
            pytest.skip("No data available, run data/indicators integration tests first")

        pred_count = await PredictionResult.find(PredictionResult.ts_code == self.ts_code).count()
        if pred_count == 0:
            pytest.skip("No predictions available, run training integration tests first")

        signal = await generate_signal(self.ts_code, strategy="price")

        assert "action" in signal
        assert signal["action"] in ["buy", "sell", "hold"]
        assert signal["current_price"] > 0
