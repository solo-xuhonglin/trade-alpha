"""Integration tests for portfolio service."""

import pytest
from trade_alpha.portfolio import service as portfolio_service


@pytest.mark.integration
@pytest.mark.order(41)
class TestPortfolioService:
    """Integration tests for portfolio service."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.default_portfolio_name = "test_portfolio"

        yield

        portfolios = portfolio_service.list_portfolios()
        for p in portfolios:
            if p["name"] != self.default_portfolio_name:
                portfolio_service.delete_portfolio(str(p["_id"]))

    def test_create_portfolio(self):
        """Test creating portfolio."""
        portfolio_id = portfolio_service.create_portfolio(
            name="test_create_temp",
            initial_capital=100000,
            buy_fee_rate=0.0003,
            sell_fee_rate=0.0003,
        )

        assert portfolio_id is not None

        portfolio = portfolio_service.get_portfolio_by_id(portfolio_id)
        assert portfolio is not None
        assert portfolio["initial_capital"] == 100000

    def test_get_portfolio(self):
        """Test getting portfolio by name."""
        portfolio_service.create_portfolio(
            name="test_get_temp",
            initial_capital=50000,
        )

        portfolio = portfolio_service.get_portfolio_by_name("test_get_temp")
        assert portfolio is not None
        assert portfolio["initial_capital"] == 50000

    def test_list_portfolios(self):
        """Test listing portfolios."""
        portfolio_service.create_portfolio(
            name="test_list_temp",
            initial_capital=80000,
        )

        portfolios = portfolio_service.list_portfolios()
        assert len(portfolios) > 0

    def test_update_portfolio(self):
        """Test updating portfolio."""
        portfolio_id = portfolio_service.create_portfolio(
            name="test_update_temp",
            initial_capital=100000,
        )

        updated = portfolio_service.update_portfolio(
            portfolio_id,
            buy_fee_rate=0.0005,
            sell_fee_rate=0.0005,
        )

        assert updated is True

        portfolio = portfolio_service.get_portfolio_by_id(portfolio_id)
        assert portfolio["buy_fee_rate"] == 0.0005

    def test_delete_portfolio(self):
        """Test deleting portfolio."""
        portfolio_id = portfolio_service.create_portfolio(
            name="test_delete_temp",
            initial_capital=100000,
        )

        deleted = portfolio_service.delete_portfolio(portfolio_id)
        assert deleted is True

        portfolio = portfolio_service.get_portfolio_by_id(portfolio_id)
        assert portfolio is None

    def test_ensure_default_portfolio(self):
        """Ensure default portfolio exists for Layer 5 tests."""
        existing = portfolio_service.get_portfolio_by_name(self.default_portfolio_name)
        if existing:
            return

        portfolio_service.create_portfolio(
            name=self.default_portfolio_name,
            initial_capital=100000,
        )
