"""Integration tests for prediction module."""

import pytest
from trade_alpha.predict.service import predict
from trade_alpha.dao import StockDaily, Prediction


@pytest.mark.integration
@pytest.mark.order(4)
class TestPredictIntegration:
    """Integration tests with real MongoDB."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Setup and teardown for each test."""
        self.ts_code = "002594.SZ"

        yield

        await Prediction.find(Prediction.ts_code == self.ts_code).delete()

    @pytest.mark.asyncio
    async def test_predict(self):
        """Test predict with existing indicators."""
        records = await StockDaily.find(StockDaily.ts_code == self.ts_code).to_list()
        assert len(records) > 0, "No data available, run data/indicators integration tests first"

        result = await predict(
            ts_code=self.ts_code,
            targets=["open", "close"],
            model="linear",
            start_date="20240101",
            end_date="20240131"
        )

        assert "open" in result
        assert "close" in result
        assert result["open"] > 0
        assert result["close"] > 0

        pred_records = await PredictionResult.find(PredictionResult.ts_code == self.ts_code).to_list()
        assert len(pred_records) > 0
