"""Pytest configuration and fixtures for integration tests."""

import asyncio
import pytest
import pytest_asyncio
from trade_alpha.dao.mongodb import init_db, close_db


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
