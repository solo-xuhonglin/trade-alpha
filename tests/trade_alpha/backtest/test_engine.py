"""Unit tests for backtest engine."""

import pytest
from unittest.mock import MagicMock
from trade_alpha.backtest.engine import BacktestEngine
from trade_alpha.portfolio import Portfolio


class TestBacktestEngine:
    """Test cases for BacktestEngine."""

    def test_run_backtest(self):
        """Test running backtest with mock data."""
        mock_records = [
            {"ts_code": "000001.SZ", "trade_date": "20240102", "open": 100.0, "close": 101.0},
            {"ts_code": "000001.SZ", "trade_date": "20240103", "open": 101.0, "close": 102.0},
            {"ts_code": "000001.SZ", "trade_date": "20240104", "open": 102.0, "close": 100.0},
        ]
        
        strategy = MagicMock()
        strategy.decide.return_value = "buy"
        
        portfolio = Portfolio(100000)
        engine = BacktestEngine("000001.SZ", "20240101", "20240131", strategy, portfolio)
        
        result = engine.run(mock_records)
        
        assert result.initial_capital == 100000
        assert result.total_trades >= 0
