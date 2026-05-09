"""Integration tests for indicators module with real environment."""

import pytest
from trade_alpha.indicators import calculate_and_store_ma, calculate_and_store_macd
from trade_alpha.dao import MongoDB


class TestIndicatorsIntegration:
    """Integration tests with real MongoDB."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.storage = MongoDB()
        self.ts_code = "002594.SZ"

        yield

        self.storage.close()

    def cleanup(self):
        coll = self.storage._get_collection()
        coll.delete_many({"ts_code": self.ts_code})

    @pytest.mark.order(3)
    @pytest.mark.integration
    def test_calculate_indicators(self):
        """Test calculate and store indicators."""
        records = self.storage.find_by_ts_code(self.ts_code)
        assert len(records) > 0, "No data available, run data integration test first"

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
