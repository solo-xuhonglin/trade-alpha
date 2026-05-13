"""Pytest configuration and fixtures for integration tests."""

import asyncio
import pytest
import pytest_asyncio
from trade_alpha.dao.mongodb import init_db, close_db
from trade_alpha.dao import StockList, StockDaily
from trade_alpha.data.service import fetch_and_store_stock_list, fetch_and_store_stock_daily
from trade_alpha.indicators.service import calculate_all_indicators
from trade_alpha.predict import config_service


TEST_STOCK = "002594.SZ"


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


@pytest_asyncio.fixture(scope="module")
async def test_stock():
    """Fixture for test stock (比亚迪) with complete data and indicators.
    
    - Deletes existing test stock data
    - Fetches from Tushare
    - Calculates all indicators
    - Sets sync_status="active"
    """
    ts_code = TEST_STOCK
    
    # Cleanup
    await StockDaily.find(StockDaily.ts_code == ts_code).delete()
    await StockList.find(StockList.ts_code == ts_code).delete()
    
    # Fetch stock list
    await fetch_and_store_stock_list()
    stock = await StockList.find_one(StockList.ts_code == ts_code)
    assert stock is not None
    
    # Fetch daily data
    await fetch_and_store_stock_daily(ts_code, "20230101", "20231231")
    
    # Calculate all indicators
    await calculate_all_indicators(ts_code)
    
    # Set active status
    stock.sync_status = "active"
    await stock.save()
    
    yield ts_code


@pytest_asyncio.fixture(scope="session")
async def test_model_config():
    """Fixture for test model config (xgboost, classification).
    
    Creates or ensures default model config exists.
    """
    default_config_name = "test_model_config"
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
