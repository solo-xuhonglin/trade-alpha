"""Integration tests for strategy service."""

import pytest
from trade_alpha.strategy import service as strategy_service
from trade_alpha.test_config import TEST_STRATEGY_NAME


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
            if s.name.endswith("_temp"):
                await strategy_service.delete_strategy(s.id)

    @pytest.mark.asyncio
    async def test_create_strategy(self):
        """Test creating single stock strategy."""
        strategy = await strategy_service.create_strategy(
            name="test_create_temp",
            strategy_type="single",
            min_order_value=5000,
            stop_loss_pct=-0.1,
            max_hold_days=30,
        )

        assert strategy is not None
        assert strategy.type == "single"
        assert strategy.min_order_value == 5000

    @pytest.mark.asyncio
    async def test_list_strategies(self):
        """Test listing strategies."""
        await strategy_service.create_strategy(
            name="test_list_temp",
            strategy_type="single",
        )

        strategies = await strategy_service.list_strategies()
        assert len(strategies) > 0

    @pytest.mark.asyncio
    async def test_update_strategy(self):
        """Test updating strategy."""
        strategy = await strategy_service.create_strategy(
            name="test_update_temp",
            strategy_type="single",
            min_order_value=5000,
            stop_loss_pct=-0.1,
        )

        updated = await strategy_service.update_strategy(
            strategy.id,
            min_order_value=10000,
            stop_loss_pct=-0.15,
        )

        assert updated is not None
        assert updated.min_order_value == 10000
        assert updated.stop_loss_pct == -0.15

    @pytest.mark.asyncio
    async def test_delete_strategy(self):
        """Test deleting strategy."""
        strategy = await strategy_service.create_strategy(
            name="test_delete_temp",
            strategy_type="single",
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
        )
