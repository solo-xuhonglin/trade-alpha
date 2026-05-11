"""Unit tests for backtest service."""

import pytest
from unittest.mock import MagicMock, patch
from trade_alpha.backtest.service import save_backtest, save_trades
from trade_alpha.backtest.engine import BacktestResult
from trade_alpha.account import TradeRecord


class TestBacktestServicePersistence:
    """Test cases for backtest persistence functions."""

    @patch("trade_alpha.backtest.service.MongoDB")
    def test_save_backtest(self, mock_mongo):
        """Test saving backtest result."""
        mock_collection = MagicMock()
        mock_mongo.return_value._get_collection.return_value = mock_collection
        mock_collection.insert_one.return_value.inserted_id = "507f1f77bcf86cd799439011"

        result = BacktestResult(
            backtest_id="",
            account_config_id="507f1f77bcf86cd799439012",
            ts_code="000001.SZ",
            start_date="20240101",
            end_date="20240131",
            strategy="price",
            initial_capital=100000,
            final_value=105000,
            total_return=0.05,
            annual_return=0.6,
            benchmark_return=0.1,
            max_drawdown=0.1,
            sharpe_ratio=1.5,
            win_rate=0.6,
            total_trades=10,
            total_fees=100,
        )

        backtest_id = save_backtest(result)

        assert backtest_id == "507f1f77bcf86cd799439011"
        mock_collection.insert_one.assert_called_once()

    @patch("trade_alpha.backtest.service.MongoDB")
    def test_save_trades(self, mock_mongo):
        """Test saving trade records."""
        mock_collection = MagicMock()
        mock_mongo.return_value._get_collection.return_value = mock_collection

        trades = [
            TradeRecord(
                date="20240102",
                action="buy",
                price=100.0,
                shares=100,
                fee=5.0,
                cash_after=89995.0,
                position_after=100,
            ),
            TradeRecord(
                date="20240105",
                action="sell",
                price=105.0,
                shares=100,
                fee=15.8,
                cash_after=94979.2,
                position_after=0,
            ),
        ]

        save_trades("507f1f77bcf86cd799439011", "507f1f77bcf86cd799439012", trades)

        assert mock_collection.insert_many.call_count == 1
