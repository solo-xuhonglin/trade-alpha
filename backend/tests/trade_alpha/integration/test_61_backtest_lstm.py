"""Integration tests for LSTM backtest — shares single backtest execution."""

import pytest
import pytest_asyncio
from trade_alpha.execution.backtest_pipeline import BacktestPipeline
from trade_alpha.execution.backtest_service import delete_execution_by_name
from trade_alpha.dao.account_config import AccountConfig
from trade_alpha.dao.strategy_config import StrategyConfig
from trade_alpha.dao.model_config import ModelConfig
from trade_alpha.dao.execution import ExecutionResult
from trade_alpha.models.training import trainer
from trade_alpha.test_config import TEST_STOCK


@pytest.mark.integration
@pytest.mark.order(61)
class TestBacktestLSTM:
    """Integration tests for LSTM backtesting — single shared execution."""

    _backtest_result = None

    @pytest_asyncio.fixture(autouse=True)
    async def setup(self):
        """Setup shared resources."""
        self.ts_code = TEST_STOCK
        self.backtest_name = "test_backtest_lstm"

        self.account_config = await AccountConfig.find_one(
            AccountConfig.name == "test_account_config"
        )
        self.strategy_config = await StrategyConfig.find_one(
            StrategyConfig.name == "test_strategy"
        )
        self.training = await self._find_training()
        self.model_config = await ModelConfig.get(self.training.config_id) if self.training else None

        yield

    async def _find_training(self):
        """Find the LSTM training created by test_53."""
        trainings = await trainer.list_trainings()
        for t in trainings:
            if t.name == "test_lstm_training":
                return t
        pytest.skip("No test_lstm_training found — test_53 must run before test_61")
        return None

    @pytest.mark.asyncio
    async def test_run_backtest(self):
        """Run LSTM backtest once and store result for subsequent tests."""
        if not all([self.account_config, self.strategy_config, self.training, self.model_config]):
            pytest.skip("Missing dependencies")

        if TestBacktestLSTM._backtest_result is not None:
            pytest.skip("Backtest already executed")

        await delete_execution_by_name(self.backtest_name)

        pipeline = BacktestPipeline(
            account_config=self.account_config,
            training_id=self.training.id,
            model_config=self.model_config,
            strategy_config=self.strategy_config,
            mode="single",
            ts_codes=[self.ts_code],
        )

        result = await pipeline.run_backtest(
            start_date="20240101",
            end_date="20240131",
            name=self.backtest_name,
            task_id=None,
        )

        TestBacktestLSTM._backtest_result = result
        assert result is not None
        assert result.name == self.backtest_name
        assert result.mode == "backtest"

    @pytest.mark.asyncio
    async def test_backtest_result_exists(self):
        """Verify backtest result exists."""
        if TestBacktestLSTM._backtest_result is None:
            pytest.skip("Backtest not executed")

        result = TestBacktestLSTM._backtest_result
        assert result.id is not None
        assert result.name == self.backtest_name
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_backtest_metrics(self):
        """Verify backtest metrics are computed."""
        if TestBacktestLSTM._backtest_result is None:
            pytest.skip("Backtest not executed")

        result = TestBacktestLSTM._backtest_result

        assert result.initial_capital is not None
        assert result.final_value is not None
        assert result.total_return is not None
        assert result.max_drawdown is not None
        assert result.total_trades is not None
        assert result.total_fees is not None

        assert isinstance(result.total_return, (int, float))
        assert isinstance(result.max_drawdown, (int, float))
        assert isinstance(result.total_trades, int)

    @pytest.mark.asyncio
    async def test_list_backtest_results(self):
        """Verify backtest results can be listed."""
        result = TestBacktestLSTM._backtest_result
        if result is None:
            pytest.skip("Backtest not executed")

        results = await ExecutionResult.find(
            ExecutionResult.name == self.backtest_name
        ).to_list()
        assert len(results) >= 1

        found = False
        for r in results:
            if r.name == self.backtest_name:
                found = True
                break
        assert found, f"Backtest result '{self.backtest_name}' not found"
