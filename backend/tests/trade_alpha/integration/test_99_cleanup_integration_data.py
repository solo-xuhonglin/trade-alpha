"""Integration test — cleanup test data by name.

Runs last (order 99) to clean up test data created by earlier integration tests.
Only removes records with known test names, leaving all other data untouched.
"""

import pytest
from trade_alpha.execution.backtest_service import delete_execution_by_name
from trade_alpha.models.training import config as config_service
from trade_alpha.models.training import trainer as training_service
from trade_alpha.test_config import TEST_MODEL_CONFIG_NAME


BACKTEST_NAME = "test_backtest_lstm"
XGB_TRAINING_NAME = "test_training"
LSTM_TRAINING_NAME = "test_lstm_training"
LSTM_CONFIG_NAME = "test_lstm_config"


@pytest.mark.integration
@pytest.mark.order(99)
class TestCleanupIntegrationData:
    """Clean up integration test records by well-known names."""

    @pytest.mark.asyncio
    async def test_cleanup_backtest(self):
        """Remove backtest execution: test_backtest_lstm."""
        deleted = await delete_execution_by_name(BACKTEST_NAME)
        if deleted:
            print(f"  Cleaned: backtest '{BACKTEST_NAME}'")
        else:
            print(f"  Not found: backtest '{BACKTEST_NAME}'")

    @pytest.mark.asyncio
    async def test_cleanup_xgboost_training(self):
        """Remove XGBoost training: test_training (including predictions and model files)."""
        deleted = await training_service.delete_training_by_name(XGB_TRAINING_NAME)
        if deleted:
            print(f"  Cleaned: training '{XGB_TRAINING_NAME}'")
        else:
            print(f"  Not found: training '{XGB_TRAINING_NAME}'")

    @pytest.mark.asyncio
    async def test_cleanup_lstm_training(self):
        """Remove LSTM training: test_lstm_training (including predictions and model files)."""
        deleted = await training_service.delete_training_by_name(LSTM_TRAINING_NAME)
        if deleted:
            print(f"  Cleaned: training '{LSTM_TRAINING_NAME}'")
        else:
            print(f"  Not found: training '{LSTM_TRAINING_NAME}'")

    @pytest.mark.asyncio
    async def test_cleanup_xgboost_config(self):
        """Remove XGBoost model config: test_model_config."""
        await _delete_config_by_name(TEST_MODEL_CONFIG_NAME, "config")

    @pytest.mark.asyncio
    async def test_cleanup_lstm_config(self):
        """Remove LSTM model config: test_lstm_config."""
        await _delete_config_by_name(LSTM_CONFIG_NAME, "LSTM config")


async def _delete_config_by_name(name: str, label: str) -> None:
    """Delete a model config by name if it exists."""
    cfg = await config_service.get_config_by_name(name)
    if cfg:
        await config_service.delete_config(cfg.id)
        print(f"  Cleaned: {label} '{name}'")
    else:
        print(f"  Not found: {label} '{name}'")