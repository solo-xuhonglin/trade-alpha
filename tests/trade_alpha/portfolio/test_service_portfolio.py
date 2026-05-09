"""Unit tests for portfolio service."""

import pytest
from unittest.mock import MagicMock, patch
from trade_alpha.portfolio.service import (
    create_portfolio,
    get_portfolio,
    get_portfolio_by_id,
    get_or_create_portfolio,
)


class TestPortfolioService:
    """Test cases for portfolio service."""

    @patch("trade_alpha.portfolio.service.MongoDB")
    def test_create_portfolio(self, mock_mongo):
        """Test creating portfolio."""
        mock_collection = MagicMock()
        mock_mongo.return_value._get_collection.return_value = mock_collection
        mock_collection.insert_one.return_value.inserted_id = "test_id"

        portfolio_id = create_portfolio("test_portfolio", 100000)

        assert portfolio_id == "test_id"
        mock_collection.insert_one.assert_called_once()

    @patch("trade_alpha.portfolio.service.MongoDB")
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

    @patch("trade_alpha.portfolio.service.MongoDB")
    def test_get_or_create_portfolio_existing(self, mock_mongo):
        """Test get_or_create with existing portfolio."""
        mock_collection = MagicMock()
        mock_mongo.return_value._get_collection.return_value = mock_collection
        mock_collection.find_one.return_value = {
            "_id": "existing_id",
            "name": "test_portfolio",
            "initial_capital": 100000,
            "buy_fee_rate": 0.0003,
            "sell_fee_rate": 0.0003,
            "stamp_tax_rate": 0.001,
            "min_fee": 5.0,
        }

        portfolio_id, portfolio_obj = get_or_create_portfolio("test_portfolio", 100000)

        assert portfolio_id == "existing_id"
        assert portfolio_obj.initial_capital == 100000
        mock_collection.insert_one.assert_not_called()

    @patch("trade_alpha.portfolio.service.get_portfolio")
    @patch("trade_alpha.portfolio.service.create_portfolio")
    @patch("trade_alpha.portfolio.service.portfolio_to_obj")
    def test_get_or_create_portfolio_new(
        self, mock_to_obj, mock_create, mock_get
    ):
        """Test get_or_create creating new portfolio."""
        mock_get.side_effect = [None, {"_id": "new_id", "initial_capital": 100000}]
        mock_create.return_value = "new_id"
        mock_to_obj.return_value = MagicMock()

        portfolio_id, portfolio_obj = get_or_create_portfolio("new_portfolio", 100000)

        assert portfolio_id == "new_id"
        mock_create.assert_called_once()
