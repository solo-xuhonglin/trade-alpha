"""Tests for prediction service."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from trade_alpha.predict.service import predict


def _make_mock_record(data: dict) -> MagicMock:
    """Create a mock record with model_dump returning the given dict."""
    record = MagicMock()
    record.model_dump.return_value = data.copy()
    for k, v in data.items():
        setattr(record, k, v)
    return record


class TestPredictService:
    @pytest.mark.asyncio
    @patch("trade_alpha.predict.service.StockDaily.find")
    async def test_predict_with_no_data(self, mock_find):
        mock_find.return_value.to_list = AsyncMock(return_value=[])

        result = await predict("000001.SZ")

        assert result == {}

    @pytest.mark.asyncio
    @patch("trade_alpha.predict.service.PredictionResult")
    @patch("trade_alpha.predict.service.StockDaily.find")
    async def test_predict_success(self, mock_find, mock_prediction_cls):
        data = [
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
        mock_find.return_value.to_list = AsyncMock(return_value=[
            _make_mock_record(d) for d in data
        ])
        mock_prediction_cls.return_value.insert = AsyncMock()

        result = await predict("000001.SZ", targets=["open", "close"])

        assert "open" in result
        assert "close" in result
        mock_prediction_cls.return_value.insert.assert_called_once()
