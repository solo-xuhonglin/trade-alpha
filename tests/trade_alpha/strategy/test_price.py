"""Tests for price strategy."""

import pytest
from trade_alpha.strategy.base import StrategyContext
from trade_alpha.strategy.price import PriceStrategy


class TestPriceStrategy:
    def test_buy_when_price_rises(self):
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=100.0,
            prediction={"close": 110.0},
            indicators={},
        )

        strategy = PriceStrategy()
        result = strategy.decide(context)

        assert result == "buy"

    def test_hold_when_price_falls(self):
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=100.0,
            prediction={"close": 90.0},
            indicators={},
        )

        strategy = PriceStrategy()
        result = strategy.decide(context)

        assert result == "hold"

    def test_hold_when_no_prediction(self):
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=100.0,
            prediction={},
            indicators={},
        )

        strategy = PriceStrategy()
        result = strategy.decide(context)

        assert result == "hold"
