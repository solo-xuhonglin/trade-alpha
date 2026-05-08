"""Tests for fetcher module."""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from data.fetcher import fetch_stock_data


class TestFetcher:
    """Test cases for fetcher module."""

    @patch("data.fetcher.ts")
    def test_fetch_stock_data_success(self, mock_ts):
        mock_df = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240101"],
            "open": [10.0],
            "high": [11.0],
            "low": [9.5],
            "close": [10.5],
            "vol": [1000000],
        })
        mock_ts.pro.daily.return_value = mock_df

        result = fetch_stock_data("000001.SZ", "20240101", "20240101")

        assert result is not None
        assert len(result) == 1
        assert result.iloc[0]["ts_code"] == "000001.SZ"

    @patch("data.fetcher.ts")
    def test_fetch_stock_data_empty(self, mock_ts):
        mock_df = pd.DataFrame()
        mock_ts.pro.daily.return_value = mock_df

        result = fetch_stock_data("000001.SZ", "20240101", "20240101")

        assert result is None

    @patch("data.fetcher.ts")
    def test_fetch_stock_data_returns_sorted(self, mock_ts):
        mock_df = pd.DataFrame({
            "ts_code": ["000001.SZ", "000001.SZ"],
            "trade_date": ["20240102", "20240101"],
            "open": [10.0, 9.5],
            "high": [11.0, 10.5],
            "low": [9.5, 9.0],
            "close": [10.5, 10.0],
            "vol": [1000000, 900000],
        })
        mock_ts.pro.return_value.daily.return_value = mock_df

        result = fetch_stock_data("000001.SZ", "20240101", "20240102")

        assert result is not None
        assert result.iloc[0]["trade_date"] == "20240101"
