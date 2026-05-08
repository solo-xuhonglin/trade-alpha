"""Integration tests for indicators module with real environment."""

import pytest
from trade_alpha.data.service import fetch_and_store
from trade_alpha.db.storage import Storage
from trade_alpha.indicators.service import calculate_and_store_ma, calculate_and_store_macd


class TestIndicatorsIntegration:
    """Integration tests with real MongoDB."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.storage = Storage()
        self.ts_code = "002594.SZ"

        yield

        self.storage.close()

    def cleanup_data(self):
        coll = self.storage._get_collection()
        coll.delete_many({"ts_code": self.ts_code})

    @pytest.mark.integration
    def test_calculate_and_store_indicators(self):
        """Test complete flow: fetch -> store -> calculate indicators -> verify."""
        self.cleanup_data()

        count = fetch_and_store(self.ts_code, "20240101", "20240131")
        assert count > 0

        ma_count = calculate_and_store_ma(self.ts_code, periods=[5, 10])
        assert ma_count > 0

        macd_count = calculate_and_store_macd(self.ts_code)
        assert macd_count > 0

        records = self.storage.find_by_ts_code(self.ts_code)
        assert len(records) > 0

        record = records[0]
        assert "ma_5" in record
        assert "ma_10" in record
        assert "macd" in record
        assert "macd_signal" in record
        assert "macd_hist" in record

        self.cleanup_data()
