"""Integration tests for backtest service."""

import pytest
from beanie import PydanticObjectId
from trade_alpha.backtest import service as backtest_service
from trade_alpha.data.service import fetch_and_store_stock_daily
from trade_alpha.account import service as account_config_service
from trade_alpha.strategy import service as strategy_service
from trade_alpha.predict import training_service, config_service
from trade_alpha.dao import BacktestResult, BacktestTrade, BacktestPortfolioDaily


async def _ensure_default_account_config():
    """Ensure default account config exists."""
    account_configs = await account_config_service.list_account_configs()
    for p in account_configs:
        if p.name == "test_portfolio":
            return p
    return await account_config_service.create_account_config(
        name="test_portfolio",
        initial_capital=100000,
        buy_fee_rate=0.0003,
        sell_fee_rate=0.0003,
    )


async def _ensure_default_strategy():
    """Ensure default strategy exists."""
    strategies = await strategy_service.list_strategies()
    for s in strategies:
        if s.name == "test_strategy":
            return s
    return await strategy_service.create_strategy(
        name="test_strategy",
        strategy_type="price",
        config={"buy_threshold": 0.02, "sell_threshold": -0.02},
    )


async def _ensure_default_config():
    """Ensure default config exists."""
    configs = await config_service.list_configs()
    for c in configs:
        if c.name == "test_model_config":
            return c
    return await config_service.create_config(
        name="test_model_config",
        model_type="linear",
        params={},
        targets=["open", "close", "high", "low"],
    )


async def _ensure_default_training(config_id: PydanticObjectId):
    """Ensure default training exists."""
    trainings = await training_service.list_trainings(config_id=config_id)
    for t in trainings:
        if t.name == "test_training":
            return t
    return await training_service.create_training(
        config_id=config_id,
        name="test_training",
        ts_codes=["002594.SZ"],
        start_date="20230101",
        end_date="20231231",
    )


@pytest.mark.integration
@pytest.mark.order(60)
class TestBacktest:
    """Integration tests for backtest service."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Setup and teardown for each test."""
        self.ts_code = "002594.SZ"
        self.start_date = "20230101"
        self.end_date = "20231231"

        await fetch_and_store_stock_daily(self.ts_code, self.start_date, self.end_date)

        account_config = await _ensure_default_account_config()
        strategy = await _ensure_default_strategy()
        config = await _ensure_default_config()
        training = await _ensure_default_training(config.id)

        self.account_config_id = account_config.id
        self.strategy_id = strategy.id
        self.training_id = training.id

        yield

        backtests = await BacktestResult.find(BacktestResult.ts_code == self.ts_code).to_list()
        for bt in backtests:
            await BacktestTrade.find(BacktestTrade.backtest_id == bt.id).delete()
            await BacktestPortfolioDaily.find(BacktestPortfolioDaily.backtest_id == bt.id).delete()
        await BacktestResult.find(BacktestResult.ts_code == self.ts_code).delete()

    @pytest.mark.asyncio
    async def test_run_backtest(self, setup_db):
        """Test running backtest."""
        result = await backtest_service.run_backtest(
            ts_code=self.ts_code,
            start_date=self.start_date,
            end_date=self.end_date,
            account_config_id=self.account_config_id,
            strategy_id=self.strategy_id,
            training_id=self.training_id,
        )

        assert result is not None
        assert result.final_value > 0
        assert result.total_trades >= 0

    @pytest.mark.asyncio
    async def test_run_backtest_with_ma_strategy(self, setup_db):
        """Test running backtest with MA strategy."""
        result = await backtest_service.run_backtest(
            ts_code=self.ts_code,
            start_date=self.start_date,
            end_date=self.end_date,
            account_config_id=self.account_config_id,
            strategy_id=self.strategy_id,
            training_id=self.training_id,
        )

        assert result is not None
        assert result.strategy_id == str(self.strategy_id)

    @pytest.mark.asyncio
    async def test_backtest_persistence(self, setup_db):
        """Test backtest result is saved."""
        result = await backtest_service.run_backtest(
            ts_code=self.ts_code,
            start_date=self.start_date,
            end_date=self.end_date,
            account_config_id=self.account_config_id,
            strategy_id=self.strategy_id,
            training_id=self.training_id,
        )

        assert result.backtest_id is not None

        saved = await BacktestResult.get(PydanticObjectId(result.backtest_id))
        assert saved is not None

    @pytest.mark.asyncio
    async def test_backtest_trades_saved(self, setup_db):
        """Test trades are saved during backtest."""
        result = await backtest_service.run_backtest(
            ts_code=self.ts_code,
            start_date=self.start_date,
            end_date=self.end_date,
            account_config_id=self.account_config_id,
            strategy_id=self.strategy_id,
            training_id=self.training_id,
        )

        if result.total_trades > 0:
            trades = await BacktestTrade.find(
                BacktestTrade.backtest_id == PydanticObjectId(result.backtest_id)
            ).to_list()
            assert len(trades) == result.total_trades

    @pytest.mark.asyncio
    async def test_backtest_metrics(self, setup_db):
        """Test backtest metrics calculation."""
        result = await backtest_service.run_backtest(
            ts_code=self.ts_code,
            start_date=self.start_date,
            end_date=self.end_date,
            account_config_id=self.account_config_id,
            strategy_id=self.strategy_id,
            training_id=self.training_id,
        )

        assert result.total_return is not None
        assert result.max_drawdown is not None
        assert result.sharpe_ratio is not None

    @pytest.mark.asyncio
    async def test_backtest_snapshots_saved(self, setup_db):
        """Test account and strategy snapshots are saved."""
        result = await backtest_service.run_backtest(
            ts_code=self.ts_code,
            start_date=self.start_date,
            end_date=self.end_date,
            account_config_id=self.account_config_id,
            strategy_id=self.strategy_id,
            training_id=self.training_id,
        )

        backtest = await BacktestResult.get(PydanticObjectId(result.backtest_id))
        assert backtest is not None
        assert backtest.account_snapshot is not None
        assert backtest.strategy_snapshot is not None
        assert backtest.account_snapshot.name is not None
        assert backtest.strategy_snapshot.name is not None

    @pytest.mark.asyncio
    async def test_backtest_daily_snapshots_saved(self, setup_db):
        """Test daily snapshots are saved."""
        result = await backtest_service.run_backtest(
            ts_code=self.ts_code,
            start_date=self.start_date,
            end_date=self.end_date,
            account_config_id=self.account_config_id,
            strategy_id=self.strategy_id,
            training_id=self.training_id,
        )

        snapshots = await BacktestPortfolioDaily.find(
            BacktestPortfolioDaily.backtest_id == PydanticObjectId(result.backtest_id)
        ).to_list()

        assert len(snapshots) > 0
        for snapshot in snapshots:
            assert snapshot.date is not None
            assert snapshot.cash is not None
            assert snapshot.total_value is not None
            assert snapshot.position_ratio is not None
