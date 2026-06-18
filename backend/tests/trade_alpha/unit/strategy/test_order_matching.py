"""Tests for T+1 order matching logic."""
from typing import Optional
from trade_alpha.schemas import PendingOrder


class FakeBaseStrategy:
    """Minimal stand-in for BaseStrategy.match_order."""

    @staticmethod
    def match_order(order: PendingOrder, open_px: float, high_px: float, low_px: float) -> Optional[float]:
        if order.order_shares > 0:  # Buy
            if order.order_price >= open_px:
                return open_px
            if high_px >= order.order_price:
                return order.order_price
            return None
        else:  # Sell
            if order.order_price <= open_px:
                return open_px
            if low_px <= order.order_price:
                return order.order_price
            return None


def test_buy_bid_above_open_fills_at_open():
    """Buy: bid price >= open -> filled at open."""
    order = PendingOrder(ts_code="000001.SZ", stock_name="Test", order_price=10.5, order_shares=100,
                          entry_score=0.8, up_prob_3d=0.6, up_prob_5d=0.55, trade_date="20250102", settle_date="20250103")
    result = FakeBaseStrategy.match_order(order, open_px=10.2, high_px=10.8, low_px=10.1)
    assert result == 10.2


def test_buy_bid_below_open_high_reaches_bid():
    """Buy: bid < open, high >= bid -> filled at bid."""
    order = PendingOrder(ts_code="000001.SZ", stock_name="Test", order_price=10.0, order_shares=100,
                          entry_score=0.8, up_prob_3d=0.6, up_prob_5d=0.55, trade_date="20250102", settle_date="20250103")
    result = FakeBaseStrategy.match_order(order, open_px=10.5, high_px=10.3, low_px=9.8)
    assert result == 10.0


def test_buy_bid_below_open_high_never_reaches():
    """Buy: bid < open, high < bid -> not filled."""
    order = PendingOrder(ts_code="000001.SZ", stock_name="Test", order_price=10.0, order_shares=100,
                          entry_score=0.8, up_prob_3d=0.6, up_prob_5d=0.55, trade_date="20250102", settle_date="20250103")
    result = FakeBaseStrategy.match_order(order, open_px=10.5, high_px=9.8, low_px=9.5)
    assert result is None


def test_sell_ask_below_open_fills_at_open():
    """Sell: ask <= open -> filled at open."""
    order = PendingOrder(ts_code="000001.SZ", stock_name="Test", order_price=10.0, order_shares=-100,
                          entry_score=0.8, up_prob_3d=0.6, up_prob_5d=0.55, trade_date="20250102", settle_date="20250103")
    result = FakeBaseStrategy.match_order(order, open_px=10.2, high_px=10.5, low_px=9.9)
    assert result == 10.2


def test_sell_ask_above_open_low_reaches_ask():
    """Sell: ask > open, low <= ask -> filled at ask."""
    order = PendingOrder(ts_code="000001.SZ", stock_name="Test", order_price=10.5, order_shares=-100,
                          entry_score=0.8, up_prob_3d=0.6, up_prob_5d=0.55, trade_date="20250102", settle_date="20250103")
    result = FakeBaseStrategy.match_order(order, open_px=10.2, high_px=10.8, low_px=10.3)
    assert result == 10.5


def test_sell_ask_above_open_low_never_reaches():
    """Sell: ask > open, low > ask -> not filled."""
    order = PendingOrder(ts_code="000001.SZ", stock_name="Test", order_price=11.0, order_shares=-100,
                          entry_score=0.8, up_prob_3d=0.6, up_prob_5d=0.55, trade_date="20250102", settle_date="20250103")
    result = FakeBaseStrategy.match_order(order, open_px=10.5, high_px=12.0, low_px=11.5)
    assert result is None
