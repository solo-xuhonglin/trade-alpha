"""Integration tests for strategy service."""

import pytest
from trade_alpha.strategy import service as strategy_service


@pytest.mark.integration
@pytest.mark.order(44)
class TestStrategyService:
    """Integration tests for strategy service."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Setup and teardown for each test."""
        self.default_strategy_name = "test_strategy"

        yield

        strategies = await strategy_service.list_strategies()
        for s in strategies:
            if s.name != self.default_strategy_name:
                await strategy_service.delete_strategy(s.id)

    @pytest.mark.asyncio
    async def test_create_strategy(self):
        """Test creating single stock strategy."""
        strategy = await strategy_service.create_strategy(
            name="test_create_temp",
            strategy_type="single",
            config={"target_ts_code": "002594.SZ"},
        )

        assert strategy is not None
        assert strategy.type == "single"

    @pytest.mark.asyncio
    async def test_list_strategies(self):
        """Test listing strategies."""
        await strategy_service.create_strategy(
            name="test_list_temp",
            strategy_type="single",
            config={},
        )

        strategies = await strategy_service.list_strategies()
        assert len(strategies) > 0

    @pytest.mark.asyncio
    async def test_update_strategy(self):
        """Test updating strategy."""
        strategy = await strategy_service.create_strategy(
            name="test_update_temp",
            strategy_type="single",
            config={"target_ts_code": "002594.SZ"},
        )

        updated = await strategy_service.update_strategy(
            strategy.id,
            config={"target_ts_code": "000001.SZ"},
        )

        assert updated is not None
        assert updated.config["target_ts_code"] == "000001.SZ"

    @pytest.mark.asyncio
    async def test_delete_strategy(self):
        """Test deleting strategy."""
        strategy = await strategy_service.create_strategy(
            name="test_delete_temp",
            strategy_type="single",
            config={},
        )

        deleted = await strategy_service.delete_strategy(strategy.id)
        assert deleted is True

        result = await strategy_service.get_strategy_by_id(strategy.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_ensure_default_strategy(self):
        """Ensure default strategy exists for Layer 5 tests."""
        strategies = await strategy_service.list_strategies()
        for s in strategies:
            if s.name == self.default_strategy_name:
                return

        await strategy_service.create_strategy(
            name=self.default_strategy_name,
            strategy_type="single",
            config={},
        )
