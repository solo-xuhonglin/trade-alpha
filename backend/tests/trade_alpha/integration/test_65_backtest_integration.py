"""Integration tests for backtest module."""

import pytest
from beanie import PydanticObjectId
from trade_alpha.backtest import service as backtest_service
from trade_alpha.data.service import fetch_and_store_stock_daily
from trade_alpha.account import service as account_config_service
from trade_alpha.strategy import service as strategy_service
from trade_alpha.predict import training_service, config_service
from trade_alpha.dao import BacktestResult, BacktestTrade, StockDaily


async def _ensure_default_training(config_id: PydanticObjectId):
    """Ensure default training exists."""
    trainings = await training_service.list_trainings(config_id=config_id)
    for t in trainings:
        if t.name == "test_backtest_training":
            return t
    return await training_service.create_training(
        config_id=config_id,
        name="test_backtest_training",
        ts_codes=["002594.SZ"],
        start_date="20230101",
        end_date="20231231",
    )


@pytest.mark.integration
@pytest.mark.order(65)
class TestBacktestIntegration:
    """Integration tests with real MongoDB."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Setup and teardown for each test."""
        self.ts_code = "002594.SZ"
        self.start_date = "20240101"
        self.end_date = "20240131"

        await fetch_and_store_stock_daily(self.ts_code, self.start_date, self.end_date)

        account_config = await account_config_service.get_account_config_by_name("test_portfolio")
        assert account_config is not None, "No default account config 'test_portfolio', please run full integration tests (Layer 41 first)"

        strategy = await strategy_service.get_strategy_by_name("test_strategy")
        assert strategy is not None, "No default strategy 'test_strategy', please run full integration tests (Layer 42 first)"

        config = await config_service.get_config_by_name("test_model_config")
        assert config is not None, "No default model config 'test_model_config', please run full integration tests (Layer 43 first)"

        training = await _ensure_default_training(config.id)

        self.account_config_id = account_config.id
        self.account_config_name = account_config.name
        self.strategy_id = strategy.id
        self.training_id = training.id

        yield

        backtests = await BacktestResult.find(BacktestResult.ts_code == self.ts_code).to_list()
        for bt in backtests:
            await BacktestTrade.find(BacktestTrade.backtest_id == bt.id).delete()
        await BacktestResult.find(BacktestResult.ts_code == self.ts_code).delete()

    @pytest.mark.asyncio
    async def test_run_backtest(self, setup_db):
        """Test running backtest with real data from MongoDB."""
        records = await StockDaily.find(StockDaily.ts_code == self.ts_code).to_list()
        assert len(records) > 0, "No data available, please run full integration tests (Layer 3 first)"

        result = await backtest_service.run_backtest(
            ts_code=self.ts_code,
            start_date=self.start_date,
            end_date=self.end_date,
            account_config_id=self.account_config_id,
            strategy_id=self.strategy_id,
            training_id=self.training_id,
        )

        assert result.backtest_id is not None
        assert result.account_config_id is not None
        assert result.ts_code == self.ts_code
        assert result.initial_capital == 100000
        assert result.final_value > 0
        assert isinstance(result.total_return, float)

        saved_backtest = await BacktestResult.get(PydanticObjectId(result.backtest_id))
        assert saved_backtest is not None
        assert saved_backtest.account_config_id is not None

        saved_account_config = await account_config_service.get_account_config_by_id(PydanticObjectId(result.account_config_id))
        assert saved_account_config is not None
        assert saved_account_config.name == self.account_config_name
