"""Unit tests for metrics module."""

import pytest
from trade_alpha.backtest.metrics import calculate_metrics
from trade_alpha.portfolio import Trade


class TestMetrics:
    """Test cases for metrics calculation."""

    def test_total_return(self):
        """Test total return calculation."""
        trades = []
        daily_values = [
            ("20240102", 100000),
            ("20240103", 101000),
            ("20240104", 102000),
        ]
        result = calculate_metrics(trades, daily_values, 100000, 0.05)

        assert result.total_return == pytest.approx(0.02)

    def test_max_drawdown(self):
        """Test max drawdown calculation."""
        trades = []
        daily_values = [
            ("20240102", 100000),
            ("20240103", 105000),
            ("20240104", 102000),
            ("20240105", 98000),
        ]
        result = calculate_metrics(trades, daily_values, 100000, 0.05)

        assert result.max_drawdown == pytest.approx(0.0667, abs=0.01)

    def test_win_rate(self):
        """Test win rate calculation."""
        trades = [
            Trade("20240102", "buy", 100.0, 100, 5.0, 90000, 100),
            Trade("20240103", "sell", 105.0, 100, 15.5, 104984.5, 0),
            Trade("20240104", "buy", 105.0, 100, 5.0, 94984.5, 100),
            Trade("20240105", "sell", 103.0, 100, 15.3, 103969.2, 0),
        ]
        daily_values = [("20240102", 100000)] * 4
        result = calculate_metrics(trades, daily_values, 100000, 0.05)

        assert result.win_rate == 0.5
