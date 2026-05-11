"""Unit tests for account config service."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from beanie import PydanticObjectId
from trade_alpha.account.service import (
    create_account_config,
    get_account_config_by_id,
    get_account_config_by_name,
    list_account_configs,
    get_or_create_account_config,
)


class TestAccountConfigService:
    """Test cases for account config service."""

    @pytest.mark.asyncio
    async def test_create_account_config(self):
        mock_account_config = MagicMock()
        mock_account_config.id = PydanticObjectId()

        with patch("trade_alpha.account.service.AccountConfig") as MockAccountConfig:
            MockAccountConfig.find_one = AsyncMock(return_value=None)
            mock_account_config.insert = AsyncMock()
            MockAccountConfig.return_value = mock_account_config

            result = await create_account_config("test_account_config", 100000)

            assert result is not None
            mock_account_config.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_account_config_duplicate_name(self):
        mock_existing = MagicMock()

        with patch("trade_alpha.account.service.AccountConfig") as MockAccountConfig:
            MockAccountConfig.find_one = AsyncMock(return_value=mock_existing)

            with pytest.raises(ValueError, match="already exists"):
                await create_account_config("test_account_config", 100000)

    @pytest.mark.asyncio
    async def test_get_account_config_by_id(self):
        mock_account_config = MagicMock()
        mock_account_config.id = PydanticObjectId()
        mock_account_config.name = "test_account_config"
        mock_account_config.initial_capital = 100000

        with patch("trade_alpha.account.service.AccountConfig") as MockAccountConfig:
            MockAccountConfig.get = AsyncMock(return_value=mock_account_config)

            result = await get_account_config_by_id(mock_account_config.id)

            assert result is not None
            assert result.name == "test_account_config"

    @pytest.mark.asyncio
    async def test_get_account_config_by_name(self):
        mock_account_config = MagicMock()
        mock_account_config.name = "test_account_config"
        mock_account_config.initial_capital = 100000

        with patch("trade_alpha.account.service.AccountConfig") as MockAccountConfig:
            MockAccountConfig.find_one = AsyncMock(return_value=mock_account_config)

            result = await get_account_config_by_name("test_account_config")

            assert result is not None
            assert result.name == "test_account_config"

    @pytest.mark.asyncio
    async def test_list_account_configs(self):
        mock_account_configs = [
            MagicMock(name="config1", initial_capital=100000),
            MagicMock(name="config2", initial_capital=200000),
        ]

        with patch("trade_alpha.account.service.AccountConfig") as MockAccountConfig:
            mock_find_all = MagicMock()
            mock_find_all.to_list = AsyncMock(return_value=mock_account_configs)
            MockAccountConfig.find_all = MagicMock(return_value=mock_find_all)

            result = await list_account_configs()

            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_or_create_account_config_existing(self):
        mock_account_config = MagicMock()
        mock_account_config.id = PydanticObjectId()
        mock_account_config.name = "test_account_config"
        mock_account_config.initial_capital = 100000

        with patch("trade_alpha.account.service.get_account_config_by_name", AsyncMock(return_value=mock_account_config)):
            result = await get_or_create_account_config("test_account_config", 100000)

            assert result is not None
            assert result.name == "test_account_config"

    @pytest.mark.asyncio
    async def test_get_or_create_account_config_new(self):
        mock_new_account_config = MagicMock()
        mock_new_account_config.id = PydanticObjectId()
        mock_new_account_config.name = "new_account_config"
        mock_new_account_config.initial_capital = 100000

        with patch("trade_alpha.account.service.get_account_config_by_name", AsyncMock(return_value=None)), \
             patch("trade_alpha.account.service.create_account_config", AsyncMock(return_value=mock_new_account_config)):

            result = await get_or_create_account_config("new_account_config", 100000)

            assert result is not None
            assert result.name == "new_account_config"
