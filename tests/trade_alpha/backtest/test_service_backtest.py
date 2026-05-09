"""Unit tests for backtest service."""

import pytest
from unittest.mock import MagicMock, patch
from trade_alpha.backtest.service import (
    create_portfolio,
    get_portfolio,
    save_backtest,
    save_trades,
)


class TestBacktestService:
    """Test cases for backtest service."""

    @patch("trade_alpha.backtest.service.MongoDB")
    def test_create_portfolio(self, mock_mongo):
        """Test creating portfolio."""
        mock_collection = MagicMock()
        mock_mongo.return_value._get_collection.return_value = mock_collection
        mock_collection.insert_one.return_value.inserted_id = "test_id"
        
        portfolio_id = create_portfolio("test_portfolio", 100000)
        
        assert portfolio_id == "test_id"
        mock_collection.insert_one.assert_called_once()

    @patch("trade_alpha.backtest.service.MongoDB")
    def test_get_portfolio(self, mock_mongo):
        """Test getting portfolio."""
        mock_collection = MagicMock()
        mock_mongo.return_value._get_collection.return_value = mock_collection
        mock_collection.find_one.return_value = {
            "_id": "test_id",
            "name": "test_portfolio",
            "initial_capital": 100000,
            "buy_fee_rate": 0.0003,
            "sell_fee_rate": 0.0003,
            "stamp_tax_rate": 0.001,
            "min_fee": 5.0,
        }
        
        portfolio = get_portfolio("test_portfolio")
        
        assert portfolio is not None
        assert portfolio["name"] == "test_portfolio"
