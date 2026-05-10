"""Integration tests for StockDaily Beanie model."""

import pytest
from trade_alpha.dao import StockDaily


@pytest.mark.integration
@pytest.mark.order(20)
class TestStockDaily:
    """Integration tests for StockDaily Beanie model."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Setup and teardown for each test."""
        self.ts_code = "002594.SZ"
        self.backup_ts_code = "601398.SH"

        yield

        await StockDaily.find(StockDaily.ts_code == self.ts_code).delete()
        await StockDaily.find(StockDaily.ts_code == self.backup_ts_code).delete()

    @pytest.mark.asyncio
    async def test_insert_and_find(self, setup_db):
        """Test insert and find operations."""
        records = [
            StockDaily(ts_code=self.ts_code, trade_date="20240101", open=10.0, close=10.5, high=10.8, low=9.9, vol=1000, amount=10000),
            StockDaily(ts_code=self.ts_code, trade_date="20240102", open=10.5, close=11.0, high=11.2, low=10.3, vol=1200, amount=12000),
        ]

        await StockDaily.insert_many(records)

        found = await StockDaily.find(StockDaily.ts_code == self.ts_code).to_list()
        assert len(found) >= 2
        dates = [r.trade_date for r in found]
        assert "20240101" in dates
        assert "20240102" in dates

    @pytest.mark.asyncio
    async def test_delete_by_ts_code(self, setup_db):
        """Test delete operation."""
        record = StockDaily(ts_code=self.backup_ts_code, trade_date="20240101", open=10.0, close=10.5, high=10.8, low=9.9, vol=1000, amount=10000)
        await record.insert()

        result = await StockDaily.find(StockDaily.ts_code == self.backup_ts_code).delete()
        assert result.deleted_count >= 1

        found = await StockDaily.find(StockDaily.ts_code == self.backup_ts_code).to_list()
        assert len(found) == 0
