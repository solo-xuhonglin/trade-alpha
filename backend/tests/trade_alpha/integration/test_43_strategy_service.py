"""Integration tests for strategy service."""

import pytest
from trade_alpha.strategy import service as strategy_service
from trade_alpha.data import fetch_and_store_stock_daily


@pytest.mark.integration
@pytest.mark.order(43)
class TestStrategyService:
    """Integration tests for strategy service."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.ts_code = "002594.SZ"
        self.start_date = "20230101"
        self.end_date = "20231231"
        self.default_strategy_name = "test_strategy"

        fetch_and_store_stock_daily(self.ts_code, self.start_date, self.end_date)

        yield

        strategies = strategy_service.list_strategies()
        for s in strategies:
            if s["name"] != self.default_strategy_name:
                strategy_service.delete_strategy(str(s["_id"]))

    def test_create_strategy(self):
        """Test creating strategy."""
        strategy_id = strategy_service.create_strategy(
            name="test_create_temp",
            strategy_type="price",
            config={"buy_threshold": 0.02, "sell_threshold": -0.02},
        )

        assert strategy_id is not None

        strategy = strategy_service.get_strategy_by_id(strategy_id)
        assert strategy is not None
        assert strategy["type"] == "price"

    def test_create_ma_strategy(self):
        """Test creating MA strategy."""
        strategy_id = strategy_service.create_strategy(
            name="test_ma_temp",
            strategy_type="ma",
            config={"short_window": 5, "long_window": 20},
        )

        assert strategy_id is not None

        strategy = strategy_service.get_strategy_by_id(strategy_id)
        assert strategy["type"] == "ma"

    def test_list_strategies(self):
        """Test listing strategies."""
        strategy_service.create_strategy(
            name="test_list_temp",
            strategy_type="price",
            config={},
        )

        strategies = strategy_service.list_strategies()
        assert len(strategies) > 0

    def test_update_strategy(self):
        """Test updating strategy."""
        strategy_id = strategy_service.create_strategy(
            name="test_update_temp",
            strategy_type="price",
            config={"buy_threshold": 0.01},
        )

        updated = strategy_service.update_strategy(
            strategy_id,
            config={"buy_threshold": 0.03},
        )

        assert updated is True

        strategy = strategy_service.get_strategy_by_id(strategy_id)
        assert strategy["config"]["buy_threshold"] == 0.03

    def test_delete_strategy(self):
        """Test deleting strategy."""
        strategy_id = strategy_service.create_strategy(
            name="test_delete_temp",
            strategy_type="price",
            config={},
        )

        deleted = strategy_service.delete_strategy(strategy_id)
        assert deleted is True

        strategy = strategy_service.get_strategy_by_id(strategy_id)
        assert strategy is None

    def test_generate_signal(self):
        """Test generating trading signal."""
        strategy_service.create_strategy(
            name="test_signal_temp",
            strategy_type="price",
            config={"buy_threshold": 0.02, "sell_threshold": -0.02},
        )

        result = strategy_service.generate_signal(
            ts_code=self.ts_code,
            strategy="price",
            strategy_config={"buy_threshold": 0.02, "sell_threshold": -0.02},
        )

        assert "action" in result

    def test_ensure_default_strategy(self):
        """Ensure default strategy exists for Layer 5 tests."""
        strategies = strategy_service.list_strategies()
        for s in strategies:
            if s["name"] == self.default_strategy_name:
                return

        strategy_service.create_strategy(
            name=self.default_strategy_name,
            strategy_type="price",
            config={"buy_threshold": 0.02, "sell_threshold": -0.02},
        )
