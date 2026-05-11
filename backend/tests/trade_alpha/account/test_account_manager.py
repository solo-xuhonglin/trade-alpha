"""Unit tests for AccountManager."""

import pytest
from trade_alpha.account import AccountManager, TradeRecord


class TestAccountManager:
    """Test cases for AccountManager class."""

    def test_initial_balance(self):
        manager = AccountManager(100000)
        assert manager.cash == 100000
        assert manager.position == 0

    def test_buy(self):
        manager = AccountManager(100000)
        trade = manager.buy("20240102", 100.0, 100)
        assert trade.action == "buy"
        assert trade.shares == 100
        assert trade.price == 100.0
        assert manager.position == 100
        assert manager.cash < 100000

    def test_sell(self):
        manager = AccountManager(100000)
        manager.buy("20240102", 100.0, 100)
        trade = manager.sell("20240103", 105.0, 100)
        assert trade.action == "sell"
        assert manager.position == 0
        assert manager.cash > 90000

    def test_fee_calculation(self):
        manager = AccountManager(100000)
        trade = manager.buy("20240102", 100.0, 10)
        assert trade.fee == 5.0
