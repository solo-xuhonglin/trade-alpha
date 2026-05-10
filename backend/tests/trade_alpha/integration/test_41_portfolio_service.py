"""Integration tests for portfolio service."""

import pytest
from trade_alpha.portfolio import service as portfolio_service


@pytest.mark.integration
@pytest.mark.order(41)
class TestPortfolioService:
    """Integration tests for portfolio service."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Setup and teardown for each test."""
        self.default_portfolio_name = "test_portfolio"

        yield

        portfolios = await portfolio_service.list_portfolios()
        for p in portfolios:
            if p.name != self.default_portfolio_name:
                await portfolio_service.delete_portfolio(p.id)

    @pytest.mark.asyncio
    async def test_create_portfolio(self):
        """Test creating portfolio."""
        portfolio = await portfolio_service.create_portfolio(
            name="test_create_temp",
            initial_capital=100000,
            buy_fee_rate=0.0003,
            sell_fee_rate=0.0003,
        )

        assert portfolio is not None

        result = await portfolio_service.get_portfolio_by_id(portfolio.id)
        assert result is not None
        assert result.initial_capital == 100000

    @pytest.mark.asyncio
    async def test_get_portfolio(self):
        """Test getting portfolio by name."""
        await portfolio_service.create_portfolio(
            name="test_get_temp",
            initial_capital=50000,
        )

        portfolio = await portfolio_service.get_portfolio_by_name("test_get_temp")
        assert portfolio is not None
        assert portfolio.initial_capital == 50000

    @pytest.mark.asyncio
    async def test_list_portfolios(self):
        """Test listing portfolios."""
        await portfolio_service.create_portfolio(
            name="test_list_temp",
            initial_capital=80000,
        )

        portfolios = await portfolio_service.list_portfolios()
        assert len(portfolios) > 0

    @pytest.mark.asyncio
    async def test_update_portfolio(self):
        """Test updating portfolio."""
        portfolio = await portfolio_service.create_portfolio(
            name="test_update_temp",
            initial_capital=100000,
        )

        updated = await portfolio_service.update_portfolio(
            portfolio.id,
            buy_fee_rate=0.0005,
            sell_fee_rate=0.0005,
        )

        assert updated is not None

        result = await portfolio_service.get_portfolio_by_id(portfolio.id)
        assert result.buy_fee_rate == 0.0005

    @pytest.mark.asyncio
    async def test_delete_portfolio(self):
        """Test deleting portfolio."""
        portfolio = await portfolio_service.create_portfolio(
            name="test_delete_temp",
            initial_capital=100000,
        )

        deleted = await portfolio_service.delete_portfolio(portfolio.id)
        assert deleted is True

        result = await portfolio_service.get_portfolio_by_id(portfolio.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_ensure_default_portfolio(self):
        """Ensure default portfolio exists for Layer 5 tests."""
        existing = await portfolio_service.get_portfolio_by_name(self.default_portfolio_name)
        if existing:
            return

        await portfolio_service.create_portfolio(
            name=self.default_portfolio_name,
            initial_capital=100000,
        )
