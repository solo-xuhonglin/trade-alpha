"""Unit tests for portfolio module."""

import pytest
from trade_alpha.portfolio import Portfolio, Trade


class TestPortfolio:
    """Test cases for Portfolio class."""

    def test_initial_balance(self):
        """Test initial portfolio balance."""
        portfolio = Portfolio(100000)
        assert portfolio.cash == 100000
        assert portfolio.position == 0

    def test_buy(self):
        """Test buying shares."""
        portfolio = Portfolio(100000)
        trade = portfolio.buy("20240102", 100.0, 100)
        assert trade.action == "buy"
        assert trade.shares == 100
        assert trade.price == 100.0
        assert portfolio.position == 100
        assert portfolio.cash < 100000

    def test_sell(self):
        """Test selling shares."""
        portfolio = Portfolio(100000)
        portfolio.buy("20240102", 100.0, 100)
        trade = portfolio.sell("20240103", 105.0, 100)
        assert trade.action == "sell"
        assert portfolio.position == 0
        assert portfolio.cash > 90000

    def test_fee_calculation(self):
        """Test fee calculation with minimum fee."""
        portfolio = Portfolio(100000)
        trade = portfolio.buy("20240102", 100.0, 10)
        assert trade.fee == 5.0
