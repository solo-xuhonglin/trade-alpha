"""Integration tests for prediction module."""

import pytest
from trade_alpha.predict import predict
from trade_alpha.data.service import fetch_and_store
from trade_alpha.db.storage import Storage
from trade_alpha.indicators.service import calculate_and_store_ma, calculate_and_store_macd


class TestPredictIntegration:
    """Integration tests with real MongoDB."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.storage = Storage()
        self.ts_code = "002594.SZ"

        yield

        self.storage.close()

    def cleanup_predictions(self):
        coll = self.storage._get_collection("predictions")
        coll.delete_many({"ts_code": self.ts_code})

    @pytest.mark.integration
    def test_predict_real_data(self):
        """Test: fetch data -> calculate indicators -> predict -> verify."""
        self.cleanup_predictions()

        self.storage._get_collection("daily").delete_many({"ts_code": self.ts_code})
        fetch_count = fetch_and_store(self.ts_code, "20240101", "20240131")
        assert fetch_count > 0

        calculate_and_store_ma(self.ts_code, periods=[5, 10])
        calculate_and_store_macd(self.ts_code)

        result = predict(
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

        predictions = self.storage._get_collection("predictions")
        pred_records = list(predictions.find({"ts_code": self.ts_code}))
        assert len(pred_records) > 0
