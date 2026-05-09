"""Unit tests for indicators.service module."""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from trade_alpha.indicators.service import calculate_and_store_ma, calculate_and_store_macd


class TestService:
    """Test cases for indicators.service module."""

    @patch("trade_alpha.indicators.service.MongoDB")
    def test_calculate_and_store_ma_success(self, mock_mongo_class):
        mock_mongo = MagicMock()
        mock_mongo.find_by_ts_code.return_value = [
            {"ts_code": "000001.SZ", "trade_date": "20240101", "close": 10.0},
            {"ts_code": "000001.SZ", "trade_date": "20240102", "close": 11.0},
            {"ts_code": "000001.SZ", "trade_date": "20240103", "close": 12.0},
        ]
        mock_mongo.update_many.return_value = 3
        mock_mongo_class.return_value = mock_mongo

        result = calculate_and_store_ma("000001.SZ", periods=[2])

        assert result == 3
        mock_mongo.find_by_ts_code.assert_called_once_with("000001.SZ")
        mock_mongo.update_many.assert_called_once()

    @patch("trade_alpha.indicators.service.MongoDB")
    def test_calculate_and_store_ma_empty(self, mock_mongo_class):
        mock_mongo = MagicMock()
        mock_mongo.find_by_ts_code.return_value = []
        mock_mongo_class.return_value = mock_mongo

        result = calculate_and_store_ma("000001.SZ")

        assert result == 0

    @patch("trade_alpha.indicators.service.MongoDB")
    def test_calculate_and_store_macd_success(self, mock_mongo_class):
        mock_mongo = MagicMock()
        mock_mongo.find_by_ts_code.return_value = [
            {"ts_code": "000001.SZ", "trade_date": f"2024010{i}", "close": 10.0 + i}
            for i in range(50)
        ]
        mock_mongo.update_many.return_value = 50
        mock_mongo_class.return_value = mock_mongo

        result = calculate_and_store_macd("000001.SZ")

        assert result == 50
