"""Tests for MAStrategy."""

import pytest
from trade_alpha.strategy.ma import MAStrategy
from trade_alpha.strategy.base import StrategyContext


class TestMAStrategy:
    def test_buy_when_price_above_ma_with_threshold(self):
        strategy = MAStrategy(ma_period=20, threshold=0.01)
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=110.0,
            prediction={},
            indicators={"ma_20": 100.0},
            position=0,
        )
        assert strategy.decide(context) == "buy"

    def test_hold_when_price_above_ma_below_threshold(self):
        strategy = MAStrategy(ma_period=20, threshold=0.05)
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=103.0,
            prediction={},
            indicators={"ma_20": 100.0},
            position=0,
        )
        assert strategy.decide(context) == "hold"

    def test_sell_when_price_below_ma_with_threshold(self):
        strategy = MAStrategy(ma_period=20, threshold=0.01)
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=90.0,
            prediction={},
            indicators={"ma_20": 100.0},
            position=100,
        )
        assert strategy.decide(context) == "sell"

    def test_hold_when_no_ma_indicator(self):
        strategy = MAStrategy(ma_period=20, threshold=0.01)
        context = StrategyContext(
            ts_code="000001.SZ",
            trade_date="20240101",
            current_price=110.0,
            prediction={},
            indicators={},
            position=0,
        )
        assert strategy.decide(context) == "hold"

    def test_default_threshold(self):
        strategy = MAStrategy(ma_period=20)
        assert strategy.threshold == 0.01
        assert strategy.ma_period == 20
