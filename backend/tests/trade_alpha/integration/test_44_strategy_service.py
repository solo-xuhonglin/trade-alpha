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
        """Test creating strategy."""
        strategy = await strategy_service.create_strategy(
            name="test_create_temp",
            strategy_type="price",
            config={"buy_threshold": 0.02, "sell_threshold": -0.02},
        )

        assert strategy is not None
        assert strategy.type == "price"

    @pytest.mark.asyncio
    async def test_create_ma_strategy(self):
        """Test creating MA strategy."""
        strategy = await strategy_service.create_strategy(
            name="test_ma_temp",
            strategy_type="ma",
            config={"short_window": 5, "long_window": 20},
        )

        assert strategy is not None
        assert strategy.type == "ma"

    @pytest.mark.asyncio
    async def test_list_strategies(self):
        """Test listing strategies."""
        await strategy_service.create_strategy(
            name="test_list_temp",
            strategy_type="price",
            config={},
        )

        strategies = await strategy_service.list_strategies()
        assert len(strategies) > 0

    @pytest.mark.asyncio
    async def test_update_strategy(self):
        """Test updating strategy."""
        strategy = await strategy_service.create_strategy(
            name="test_update_temp",
            strategy_type="price",
            config={"buy_threshold": 0.01},
        )

        updated = await strategy_service.update_strategy(
            strategy.id,
            config={"buy_threshold": 0.03},
        )

        assert updated is not None
        assert updated.config["buy_threshold"] == 0.03

    @pytest.mark.asyncio
    async def test_delete_strategy(self):
        """Test deleting strategy."""
        strategy = await strategy_service.create_strategy(
            name="test_delete_temp",
            strategy_type="price",
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
            strategy_type="price",
            config={"buy_threshold": 0.02, "sell_threshold": -0.02},
        )
