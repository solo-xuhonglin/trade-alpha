"""Integration tests for strategy module."""

import pytest
from trade_alpha.indicators import calculate_and_store_ma
from trade_alpha.predict import predict
from trade_alpha.strategy import generate_signal
from trade_alpha.db.storage import Storage


@pytest.mark.integration
class TestStrategyIntegration:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.storage = Storage()
        self.ts_code = "002594.SZ"

        yield

        self.storage.close()

    def cleanup_signals(self):
        coll = self.storage._get_collection("signals")
        coll.delete_many({"ts_code": self.ts_code})

    def test_generate_signal_real_data(self):
        """Test: indicators -> predict -> signal using existing data"""
        self.cleanup_signals()

        records = self.storage.find_by_ts_code(self.ts_code)
        if not records:
            pytest.skip("No data available, run data integration test first")

        calculate_and_store_ma(self.ts_code, periods=[5, 10])

        predict(self.ts_code, targets=["close"])

        signal = generate_signal(self.ts_code, strategy="price")

        assert "action" in signal
        assert signal["action"] in ["buy", "sell", "hold"]
        assert signal["current_price"] > 0
