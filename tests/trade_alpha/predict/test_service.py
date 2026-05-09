"""Tests for prediction service."""

import pytest
from unittest.mock import MagicMock, patch
from trade_alpha.predict.service import predict


class TestPredictService:
    @patch("trade_alpha.predict.service.Storage")
    def test_predict_with_no_data(self, mock_storage_class):
        mock_storage = MagicMock()
        mock_storage.find_by_ts_code.return_value = []
        mock_storage_class.return_value = mock_storage

        result = predict("000001.SZ")

        assert result == {}
        mock_storage.close.assert_called_once()

    @patch("trade_alpha.predict.service.Storage")
    def test_predict_success(self, mock_storage_class):
        mock_storage = MagicMock()
        mock_storage.find_by_ts_code.return_value = [
            {"trade_date": "20240101", "open": 10, "high": 11, "low": 9, "close": 10.5, "vol": 100, "ma_5": 10.2},
            {"trade_date": "20240102", "open": 10.5, "high": 11.5, "low": 10, "close": 11, "vol": 110, "ma_5": 10.4},
            {"trade_date": "20240103", "open": 11, "high": 12, "low": 10.5, "close": 11.5, "vol": 120, "ma_5": 10.8},
            {"trade_date": "20240104", "open": 11.5, "high": 12.5, "low": 11, "close": 12, "vol": 130, "ma_5": 11.0},
            {"trade_date": "20240105", "open": 12, "high": 13, "low": 11.5, "close": 12.5, "vol": 140, "ma_5": 11.5},
            {"trade_date": "20240106", "open": 12.5, "high": 13.5, "low": 12, "close": 13, "vol": 150, "ma_5": 12.0},
            {"trade_date": "20240107", "open": 13, "high": 14, "low": 12.5, "close": 13.5, "vol": 160, "ma_5": 12.5},
            {"trade_date": "20240108", "open": 13.5, "high": 14.5, "low": 13, "close": 14, "vol": 170, "ma_5": 13.0},
            {"trade_date": "20240109", "open": 14, "high": 15, "low": 13.5, "close": 14.5, "vol": 180, "ma_5": 13.5},
            {"trade_date": "20240110", "open": 14.5, "high": 15.5, "low": 14, "close": 15, "vol": 190, "ma_5": 14.0},
            {"trade_date": "20240111", "open": 15, "high": 16, "low": 14.5, "close": 15.5, "vol": 200, "ma_5": 14.5},
            {"trade_date": "20240112", "open": 15.5, "high": 16.5, "low": 15, "close": 16, "vol": 210, "ma_5": 15.0},
        ]
        mock_storage_class.return_value = mock_storage

        result = predict("000001.SZ", targets=["open", "close"])

        assert "open" in result
        assert "close" in result
        mock_storage.insert_many.assert_called_once()
        mock_storage.close.assert_called_once()
