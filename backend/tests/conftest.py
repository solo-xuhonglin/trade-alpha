"""Pytest configuration and fixtures for integration tests."""

import asyncio
import pytest
import pytest_asyncio
from trade_alpha.dao.mongodb import init_db, close_db
from trade_alpha.dao import StockList
from trade_alpha.data.service import fetch_and_store_stock_list
from trade_alpha.models import training
from trade_alpha.test_config import TEST_STOCK, TEST_MODEL_CONFIG_NAME


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    """Setup database for all tests."""
    await init_db()
    yield
    await close_db()


@pytest_asyncio.fixture(scope="session")
async def ensure_test_stock():
    """Ensure BYD entry exists in StockList. Fetches from Tushare if missing.

    Only ensures StockList has BYD record with full fields (industry/market cap etc.),
    does not touch StockDaily data. Data lifecycle handled by test_20 + test_25.
    """
    ts_code = TEST_STOCK
    stock = await StockList.find_one(StockList.ts_code == ts_code)
    if not stock:
        await fetch_and_store_stock_list()
    return ts_code


@pytest_asyncio.fixture(scope="session")
async def test_model_config():
    """Fixture for test model config (xgboost, classification).

    Creates or ensures default model config exists.
    """
    default_config_name = TEST_MODEL_CONFIG_NAME
    config = await training.get_config_by_name(default_config_name)
    if config:
        await config.delete()

    config = await training.create_config(
        name=default_config_name,
        model_type="xgboost",
        classification_horizons=[3, 5],
        classification_threshold_3d=0.02,
        classification_threshold_5d=0.02,
        classification_threshold_10d=0.02,
    )
    return config


@pytest_asyncio.fixture(scope="session")
async def test_lstm_config():
    """Fixture for test LSTM model config."""
    lstm_config_name = "test_lstm_config"
    config = await training.get_config_by_name(lstm_config_name)
    if config:
        await config.delete()

    config = await training.create_config(
        name=lstm_config_name,
        model_type="lstm",
        feature_fields=[
            "ma_5", "ma_10", "ma_20",
            "macd", "macd_signal", "macd_hist",
            "pct_chg",
            "kdj_k", "kdj_d", "kdj_j",
            "rsi_6", "rsi_12"
        ],
        standardize_fields=[
            "ma_5", "ma_10", "ma_20",
            "macd", "macd_signal", "macd_hist",
            "pct_chg",
            "kdj_k", "kdj_d", "kdj_j",
            "rsi_6", "rsi_12"
        ],
        winsorize_fields=[
            "ma_5", "ma_10", "ma_20",
            "macd", "macd_signal", "macd_hist",
            "pct_chg",
            "kdj_k", "kdj_d", "kdj_j",
            "rsi_6", "rsi_12"
        ],
        classification_horizons=[3, 5],
        classification_threshold_3d=0.02,
        classification_threshold_5d=0.02,
        classification_threshold_10d=0.02,
        lstm_hidden_size=64,
        lstm_num_layers=2,
        lstm_dropout=0.2,
        lstm_epochs=5,
        lstm_batch_size=32,
        lstm_learning_rate=0.0001,
        lstm_sequence_length=10
    )
    return config
