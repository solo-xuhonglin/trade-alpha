"""Integration tests for dao module with Beanie models."""

import pytest
from datetime import datetime
from trade_alpha.dao import StockDaily, StockList, AccountConfig


@pytest.mark.integration
@pytest.mark.order(1)
class TestDAOIntegration:
    """Integration tests with Beanie models."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Setup and teardown for each test."""
        self.ts_code = "601398.SH"

        yield

        await StockDaily.find(StockDaily.ts_code == self.ts_code).delete()
        await StockList.find(StockList.ts_code == self.ts_code).delete()
        test_account_configs = await AccountConfig.find(AccountConfig.name == "test_dao_portfolio").to_list()
        for p in test_account_configs:
            await p.delete()

    @pytest.mark.asyncio
    async def test_insert_and_find_stock_daily(self):
        """Test basic StockDaily operations: insert -> find -> verify."""
        records = [
            StockDaily(
                ts_code=self.ts_code,
                trade_date="20240101",
                open=100.0,
                high=102.0,
                low=99.0,
                close=101.0,
                vol=10000.0,
                amount=1000000.0,
            ),
            StockDaily(
                ts_code=self.ts_code,
                trade_date="20240102",
                open=101.0,
                high=103.0,
                low=100.0,
                close=102.0,
                vol=12000.0,
                amount=1200000.0,
            ),
        ]

        await StockDaily.insert_many(records)

        found = await StockDaily.find(StockDaily.ts_code == self.ts_code).sort(StockDaily.trade_date).to_list()
        assert len(found) >= 2
        assert found[0].close == 101.0
        assert found[1].close == 102.0

    @pytest.mark.asyncio
    async def test_update_stock_daily(self):
        """Test update operations: insert -> update -> verify."""
        record = StockDaily(
            ts_code=self.ts_code,
            trade_date="20240101",
            open=100.0,
            high=102.0,
            low=99.0,
            close=100.0,
            vol=1000.0,
            amount=100000.0,
        )
        await record.insert()

        record.close = 105.0
        record.vol = 1500.0
        await record.save()

        found = await StockDaily.find_one(
            StockDaily.ts_code == self.ts_code,
            StockDaily.trade_date == "20240101",
        )
        assert found is not None
        assert found.close == 105.0
        assert found.vol == 1500.0

    @pytest.mark.asyncio
    async def test_insert_and_find_stock_list(self):
        """Test StockList operations."""
        stock = StockList(
            ts_code=self.ts_code,
            name="工商银行",
            market="主板",
        )
        await stock.insert()

        found = await StockList.find_one(StockList.ts_code == self.ts_code)
        assert found is not None
        assert found.name == "工商银行"

    @pytest.mark.asyncio
    async def test_insert_and_find_account_config(self):
        """Test AccountConfig operations."""
        account_config = AccountConfig(
            name="test_dao_portfolio",
            initial_capital=100000,
            buy_fee_rate=0.0003,
            sell_fee_rate=0.0003,
            stamp_tax_rate=0.001,
            min_fee=5.0,
            cash=100000,
            created_at=datetime.utcnow(),
        )
        await account_config.insert()

        found = await AccountConfig.find_one(AccountConfig.name == "test_dao_portfolio")
        assert found is not None
        assert found.initial_capital == 100000
        assert found.id is not None

    @pytest.mark.asyncio
    async def test_delete_records(self):
        """Test delete operations."""
        record = StockDaily(
            ts_code=self.ts_code,
            trade_date="20240101",
            open=100.0,
            high=102.0,
            low=99.0,
            close=100.0,
            vol=1000.0,
            amount=100000.0,
        )
        await record.insert()

        count = await StockDaily.find(StockDaily.ts_code == self.ts_code).delete()
        assert count.deleted_count == 1

        found = await StockDaily.find(StockDaily.ts_code == self.ts_code).to_list()
        assert len(found) == 0
