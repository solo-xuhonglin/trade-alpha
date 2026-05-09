"""Integration tests for prediction module."""

import pytest
from trade_alpha.predict import predict
from trade_alpha.dao import MongoDB


class TestPredictIntegration:
    """Integration tests with real MongoDB."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.storage = MongoDB()
        self.ts_code = "002594.SZ"

        yield

        self.storage.close()

    def cleanup(self):
        coll = self.storage._get_collection("predictions")
        coll.delete_many({"ts_code": self.ts_code})

    @pytest.mark.order(4)
    @pytest.mark.integration
    def test_predict(self):
        """Test predict with existing indicators."""
        records = self.storage.find_by_ts_code(self.ts_code)
        assert len(records) > 0, "No data available, run data/indicators integration tests first"

        self.cleanup()

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
