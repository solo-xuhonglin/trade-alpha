"""Tests for MACDStrategy."""

import pytest
from trade_alpha.strategy.macd import MACDStrategy
from trade_alpha.strategy.base import StrategyContext


class TestMACDStrategy:
    def test_buy_when_macd_above_signal_with_threshold(self):
        strategy = MACDStrategy(threshold=0.5)
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=100.0,
            prediction={},
            indicators={"macd": 2.0, "macd_signal": 1.0},
            position=0,
        )
        assert strategy.decide(context) == "buy"

    def test_hold_when_macd_above_signal_below_threshold(self):
        strategy = MACDStrategy(threshold=5.0)
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=100.0,
            prediction={},
            indicators={"macd": 2.0, "macd_signal": 1.0},
            position=0,
        )
        assert strategy.decide(context) == "hold"

    def test_sell_when_macd_below_signal_with_threshold(self):
        strategy = MACDStrategy(threshold=0.5)
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=100.0,
            prediction={},
            indicators={"macd": -2.0, "macd_signal": 1.0},
            position=100,
        )
        assert strategy.decide(context) == "sell"

    def test_hold_when_no_macd_indicator(self):
        strategy = MACDStrategy(threshold=0.5)
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=100.0,
            prediction={},
            indicators={},
            position=0,
        )
        assert strategy.decide(context) == "hold"

    def test_default_threshold(self):
        strategy = MACDStrategy()
        assert strategy.threshold == 0.5
