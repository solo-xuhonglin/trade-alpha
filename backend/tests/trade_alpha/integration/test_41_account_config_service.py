"""Integration tests for account config service."""

import pytest
from trade_alpha.account import service as account_config_service


@pytest.mark.integration
@pytest.mark.order(41)
class TestAccountConfigService:
    """Integration tests for account config service."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Setup and teardown for each test."""
        self.default_account_config_name = TEST_ACCOUNT_CONFIG_NAME

        yield

        account_configs = await account_config_service.list_account_configs()
        for p in account_configs:
            if p.name != self.default_account_config_name:
                await account_config_service.delete_account_config(p.id)

    @pytest.mark.asyncio
    async def test_create_account_config(self):
        """Test creating account config."""
        account_config = await account_config_service.create_account_config(
            name="test_create_temp",
            initial_capital=100000,
            buy_fee_rate=0.0003,
            sell_fee_rate=0.0003,
        )

        assert account_config is not None

        result = await account_config_service.get_account_config_by_id(account_config.id)
        assert result is not None
        assert result.initial_capital == 100000

    @pytest.mark.asyncio
    async def test_get_account_config(self):
        """Test getting account config by name."""
        await account_config_service.create_account_config(
            name="test_get_temp",
            initial_capital=50000,
        )

        account_config = await account_config_service.get_account_config_by_name("test_get_temp")
        assert account_config is not None
        assert account_config.initial_capital == 50000

    @pytest.mark.asyncio
    async def test_list_account_configs(self):
        """Test listing account configs."""
        await account_config_service.create_account_config(
            name="test_list_temp",
            initial_capital=80000,
        )

        account_configs = await account_config_service.list_account_configs()
        assert len(account_configs) > 0

    @pytest.mark.asyncio
    async def test_update_account_config(self):
        """Test updating account config."""
        account_config = await account_config_service.create_account_config(
            name="test_update_temp",
            initial_capital=100000,
        )

        updated = await account_config_service.update_account_config(
            account_config.id,
            buy_fee_rate=0.0005,
            sell_fee_rate=0.0005,
        )

        assert updated is not None

        result = await account_config_service.get_account_config_by_id(account_config.id)
        assert result.buy_fee_rate == 0.0005

    @pytest.mark.asyncio
    async def test_delete_account_config(self):
        """Test deleting account config."""
        account_config = await account_config_service.create_account_config(
            name="test_delete_temp",
            initial_capital=100000,
        )

        deleted = await account_config_service.delete_account_config(account_config.id)
        assert deleted is True

        result = await account_config_service.get_account_config_by_id(account_config.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_ensure_default_account_config(self):
        """Ensure default account config exists for Layer 5 tests."""
        existing = await account_config_service.get_account_config_by_name(self.default_account_config_name)
        if existing:
            return

        await account_config_service.create_account_config(
            name=self.default_account_config_name,
            initial_capital=100000,
        )
