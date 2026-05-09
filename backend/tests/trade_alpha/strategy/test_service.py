"""Tests for strategy service."""

import pytest
from unittest.mock import MagicMock, patch
from trade_alpha.strategy.service import generate_signal


class TestStrategyService:
    @patch("trade_alpha.strategy.service.MongoDB")
    def test_generate_signal_no_data(self, mock_mongo_class):
        mock_mongo = MagicMock()
        mock_mongo.find_by_ts_code.return_value = []
        mock_mongo_class.return_value = mock_mongo

        result = generate_signal("000001.SZ")

        assert result == {}
        mock_mongo.close.assert_called_once()

    @patch("trade_alpha.strategy.service.MongoDB")
    def test_generate_signal_success(self, mock_mongo_class):
        mock_mongo = MagicMock()
        mock_mongo.find_by_ts_code.return_value = [
            {"trade_date": "20240101", "close": 100.0},
        ]
        mock_mongo._get_collection.return_value.find.return_value.sort.return_value.limit.return_value = [
            {"target_close": 110.0}
        ]
        mock_mongo_class.return_value = mock_mongo

        result = generate_signal("000001.SZ")

        assert "action" in result
        assert result["action"] == "buy"
        mock_mongo.insert_many.assert_called_once()
        mock_mongo.close.assert_called_once()
