"""Unit tests for data.service module."""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from trade_alpha.data.service import fetch_and_store


class TestService:
    """Test cases for data.service module."""

    @patch("trade_alpha.data.service.fetch_stock_data")
    @patch("trade_alpha.data.service.MongoDB")
    def test_fetch_and_store_success(self, mock_mongo_class, mock_fetch):
        mock_df = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "close": [10.0],
        })
        mock_fetch.return_value = mock_df
        mock_mongo = MagicMock()
        mock_mongo.insert_many.return_value = 1
        mock_mongo_class.return_value = mock_mongo

        result = fetch_and_store("000001.SZ", "20240101", "20240101")

        assert result == 1
        mock_fetch.assert_called_once_with("000001.SZ", "20240101", "20240101")
        mock_mongo.insert_many.assert_called_once()

    @patch("trade_alpha.data.service.fetch_stock_data")
    def test_fetch_and_store_empty(self, mock_fetch):
        mock_fetch.return_value = None

        result = fetch_and_store("000001.SZ", "20240101", "20240101")

        assert result == 0
