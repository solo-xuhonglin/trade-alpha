"""Unit tests for portfolio service."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from beanie import PydanticObjectId
from trade_alpha.portfolio.service import (
    create_portfolio,
    get_portfolio_by_id,
    get_portfolio_by_name,
    list_portfolios,
    get_or_create_portfolio,
)


class TestPortfolioService:
    """Test cases for portfolio service."""

    @pytest.mark.asyncio
    async def test_create_portfolio(self):
        """Test creating portfolio."""
        mock_portfolio = MagicMock()
        mock_portfolio.id = PydanticObjectId()
        
        with patch("trade_alpha.portfolio.service.Portfolio") as MockPortfolio:
            MockPortfolio.find_one = AsyncMock(return_value=None)
            mock_portfolio.insert = AsyncMock()
            MockPortfolio.return_value = mock_portfolio
            
            result = await create_portfolio("test_portfolio", 100000)
            
            assert result is not None
            mock_portfolio.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_portfolio_duplicate_name(self):
        """Test creating portfolio with duplicate name."""
        mock_existing = MagicMock()
        
        with patch("trade_alpha.portfolio.service.Portfolio") as MockPortfolio:
            MockPortfolio.find_one = AsyncMock(return_value=mock_existing)
            
            with pytest.raises(ValueError, match="already exists"):
                await create_portfolio("test_portfolio", 100000)

    @pytest.mark.asyncio
    async def test_get_portfolio_by_id(self):
        """Test getting portfolio by ID."""
        mock_portfolio = MagicMock()
        mock_portfolio.id = PydanticObjectId()
        mock_portfolio.name = "test_portfolio"
        mock_portfolio.initial_capital = 100000
        
        with patch("trade_alpha.portfolio.service.Portfolio") as MockPortfolio:
            MockPortfolio.get = AsyncMock(return_value=mock_portfolio)
            
            result = await get_portfolio_by_id(mock_portfolio.id)
            
            assert result is not None
            assert result.name == "test_portfolio"

    @pytest.mark.asyncio
    async def test_get_portfolio_by_name(self):
        """Test getting portfolio by name."""
        mock_portfolio = MagicMock()
        mock_portfolio.name = "test_portfolio"
        mock_portfolio.initial_capital = 100000
        
        with patch("trade_alpha.portfolio.service.Portfolio") as MockPortfolio:
            mock_find = MagicMock()
            mock_find.find_one = AsyncMock(return_value=mock_portfolio)
            MockPortfolio.find_one = AsyncMock(return_value=mock_portfolio)
            
            result = await get_portfolio_by_name("test_portfolio")
            
            assert result is not None
            assert result.name == "test_portfolio"

    @pytest.mark.asyncio
    async def test_list_portfolios(self):
        """Test listing portfolios."""
        mock_portfolios = [
            MagicMock(name="portfolio1", initial_capital=100000),
            MagicMock(name="portfolio2", initial_capital=200000),
        ]
        
        with patch("trade_alpha.portfolio.service.Portfolio") as MockPortfolio:
            mock_find_all = MagicMock()
            mock_find_all.to_list = AsyncMock(return_value=mock_portfolios)
            MockPortfolio.find_all = MagicMock(return_value=mock_find_all)
            
            result = await list_portfolios()
            
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_or_create_portfolio_existing(self):
        """Test get_or_create with existing portfolio."""
        mock_portfolio = MagicMock()
        mock_portfolio.id = PydanticObjectId()
        mock_portfolio.name = "test_portfolio"
        mock_portfolio.initial_capital = 100000
        
        with patch("trade_alpha.portfolio.service.get_portfolio_by_name", AsyncMock(return_value=mock_portfolio)):
            result = await get_or_create_portfolio("test_portfolio", 100000)
            
            assert result is not None
            assert result.name == "test_portfolio"

    @pytest.mark.asyncio
    async def test_get_or_create_portfolio_new(self):
        """Test get_or_create creating new portfolio."""
        mock_new_portfolio = MagicMock()
        mock_new_portfolio.id = PydanticObjectId()
        mock_new_portfolio.name = "new_portfolio"
        mock_new_portfolio.initial_capital = 100000
        
        with patch("trade_alpha.portfolio.service.get_portfolio_by_name", AsyncMock(return_value=None)), \
             patch("trade_alpha.portfolio.service.create_portfolio", AsyncMock(return_value=mock_new_portfolio)):
            
            result = await get_or_create_portfolio("new_portfolio", 100000)
            
            assert result is not None
            assert result.name == "new_portfolio"
