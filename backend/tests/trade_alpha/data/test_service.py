"""Unit tests for data.service module."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import pandas as pd
from trade_alpha.data.service import fetch_and_store


class TestService:
    """Test cases for data.service module."""

    @pytest.mark.asyncio
    @patch("trade_alpha.data.service.fetch_stock_data")
    @patch("trade_alpha.data.service.StockDaily.insert_many")
    @patch("trade_alpha.data.service.StockDaily.find")
    async def test_fetch_and_store_success(self, mock_find, mock_insert_many, mock_fetch):
        mock_df = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "open": [10.5],
            "high": [11.0],
            "low": [9.5],
            "close": [10.0],
            "vol": [1000000],
            "amount": [10500000],
        })
        mock_fetch.return_value = mock_df
        mock_find.return_value.to_list = AsyncMock(return_value=[])
        mock_insert_many.return_value = None

        result = await fetch_and_store("000001.SZ", "20240101", "20240101")

        assert result == 1
        mock_fetch.assert_called_once_with("000001.SZ", "20240101", "20240101")
        mock_insert_many.assert_called_once()

    @pytest.mark.asyncio
    @patch("trade_alpha.data.service.fetch_stock_data")
    async def test_fetch_and_store_empty(self, mock_fetch):
        mock_fetch.return_value = None

        result = await fetch_and_store("000001.SZ", "20240101", "20240101")

        assert result == 0
