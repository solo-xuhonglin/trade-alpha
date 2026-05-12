"""Tests for price strategy."""

import pytest
from trade_alpha.strategy.base import StrategyContext
from trade_alpha.strategy.price import PriceStrategy


class TestPriceStrategy:
    def test_buy_when_price_rises_above_threshold(self):
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=100.0,
            prediction={"close": 102.0},
            indicators={},
            position=0,
        )

        strategy = PriceStrategy(buy_threshold=0.01, sell_threshold=0.01)
        result = strategy.decide(context)

        assert result == "buy"

    def test_hold_when_rise_below_threshold(self):
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=100.0,
            prediction={"close": 100.5},
            indicators={},
            position=0,
        )

        strategy = PriceStrategy(buy_threshold=0.01, sell_threshold=0.01)
        result = strategy.decide(context)

        assert result == "hold"

    def test_sell_when_price_falls_above_threshold(self):
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=100.0,
            prediction={"close": 98.0},
            indicators={},
            position=100,
        )

        strategy = PriceStrategy(buy_threshold=0.01, sell_threshold=0.01)
        result = strategy.decide(context)

        assert result == "sell"

    def test_hold_when_fall_below_threshold(self):
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=100.0,
            prediction={"close": 99.5},
            indicators={},
            position=100,
        )

        strategy = PriceStrategy(buy_threshold=0.01, sell_threshold=0.01)
        result = strategy.decide(context)

        assert result == "hold"

    def test_hold_when_no_prediction(self):
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=100.0,
            prediction={},
            indicators={},
            position=0,
        )

        strategy = PriceStrategy()
        result = strategy.decide(context)

        assert result == "hold"

    def test_default_threshold(self):
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=100.0,
            prediction={"close": 105.0},
            indicators={},
            position=0,
        )

        strategy = PriceStrategy()
        assert strategy.buy_threshold == 0.01
        assert strategy.sell_threshold == 0.01
        assert strategy.decide(context) == "buy"
