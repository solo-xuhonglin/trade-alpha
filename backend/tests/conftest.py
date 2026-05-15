"""Pytest configuration and fixtures for integration tests."""

import asyncio
import pytest
import pytest_asyncio
from trade_alpha.dao.mongodb import init_db, close_db
from trade_alpha.dao import StockList
from trade_alpha.data.service import fetch_and_store_stock_list
from trade_alpha.predict import config_service
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
    config = await config_service.get_config_by_name(default_config_name)
    if config:
        await config.delete()

    config = await config_service.create_config(
        name=default_config_name,
        model_type="xgboost",
        classification_horizons=[3, 5],
        classification_threshold=0.02,
    )
    return config
