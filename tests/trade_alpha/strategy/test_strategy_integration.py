"""Integration tests for strategy module."""

import pytest
from trade_alpha.strategy import generate_signal
from trade_alpha.dao import MongoDB


class TestStrategyIntegration:
    """Integration tests with real MongoDB."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.storage = MongoDB()
        self.ts_code = "002594.SZ"

        yield

        self.storage.close()

    def cleanup(self):
        coll = self.storage._get_collection("signals")
        coll.delete_many({"ts_code": self.ts_code})

    @pytest.mark.order(5)
    @pytest.mark.integration
    def test_generate_signal(self):
        """Test generate signal with existing predictions."""
        records = self.storage.find_by_ts_code(self.ts_code)
        assert len(records) > 0, "No data available, run data/indicators integration tests first"

        predictions = self.storage._get_collection("predictions")
        pred_count = predictions.count_documents({"ts_code": self.ts_code})
        assert pred_count > 0, "No predictions available, run predict integration test first"

        self.cleanup()

        signal = generate_signal(self.ts_code, strategy="price")

        assert "action" in signal
        assert signal["action"] in ["buy", "sell", "hold"]
        assert signal["current_price"] > 0
