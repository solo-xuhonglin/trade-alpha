"""Unit tests for indicators.service module."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from trade_alpha.indicators.service import (
    calculate_and_store_ma,
    calculate_and_store_macd,
    calculate_and_store_more_indicators,
)


def _make_mock_record(data: dict) -> MagicMock:
    """Create a mock record with model_dump returning the given dict."""
    record = MagicMock()
    record.model_dump.return_value = data.copy()
    for k, v in data.items():
        setattr(record, k, v)
    return record


def _make_price_records(count: int) -> list:
    """Generate mock records with high/low/close/vol for indicator tests."""
    return [
        _make_mock_record({
            "ts_code": "000001.SZ",
            "trade_date": f"2024010{i:02d}",
            "open": 10.0 + i,
            "high": 11.0 + i,
            "low": 9.0 + i,
            "close": 10.0 + i,
            "vol": 100.0 + i,
        })
        for i in range(count)
    ]


class TestService:
    """Test cases for indicators.service module."""

    @pytest.mark.asyncio
    @patch("trade_alpha.indicators.service.StockDaily.find_one")
    @patch("trade_alpha.indicators.service.StockDaily.find")
    async def test_calculate_and_store_ma_success(self, mock_find, mock_find_one):
        mock_find.return_value.to_list = AsyncMock(return_value=[
            _make_mock_record({"ts_code": "000001.SZ", "trade_date": "20240101", "close": 10.0}),
            _make_mock_record({"ts_code": "000001.SZ", "trade_date": "20240102", "close": 11.0}),
            _make_mock_record({"ts_code": "000001.SZ", "trade_date": "20240103", "close": 12.0}),
        ])
        mock_find_one.return_value.update = AsyncMock()

        result = await calculate_and_store_ma("000001.SZ", periods=[2])

        assert result == 3
        assert mock_find_one.return_value.update.call_count == 3

    @pytest.mark.asyncio
    @patch("trade_alpha.indicators.service.StockDaily.find")
    async def test_calculate_and_store_ma_empty(self, mock_find):
        mock_find.return_value.to_list = AsyncMock(return_value=[])

        result = await calculate_and_store_ma("000001.SZ")

        assert result == 0

    @pytest.mark.asyncio
    @patch("trade_alpha.indicators.service.StockDaily.find_one")
    @patch("trade_alpha.indicators.service.StockDaily.find")
    async def test_calculate_and_store_macd_success(self, mock_find, mock_find_one):
        mock_find.return_value.to_list = AsyncMock(return_value=_make_price_records(50))
        mock_find_one.return_value.update = AsyncMock()

        result = await calculate_and_store_macd("000001.SZ")

        assert result == 50

    @pytest.mark.asyncio
    @patch("trade_alpha.indicators.service.StockDaily.find_one")
    @patch("trade_alpha.indicators.service.StockDaily.find")
    async def test_calculate_and_store_more_indicators_success(self, mock_find, mock_find_one):
        mock_find.return_value.to_list = AsyncMock(return_value=_make_price_records(30))
        mock_find_one.return_value.update = AsyncMock()

        result = await calculate_and_store_more_indicators("000001.SZ")

        assert result == 30

    @pytest.mark.asyncio
    @patch("trade_alpha.indicators.service.StockDaily.find")
    async def test_calculate_and_store_more_indicators_empty(self, mock_find):
        mock_find.return_value.to_list = AsyncMock(return_value=[])

        result = await calculate_and_store_more_indicators("000001.SZ")

        assert result == 0
