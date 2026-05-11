"""Tests for strategy service."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from trade_alpha.strategy.service import generate_signal


class TestStrategyService:
    @pytest.mark.asyncio
    @patch("trade_alpha.strategy.service.StockDaily.find")
    async def test_generate_signal_no_data(self, mock_find):
        mock_find.return_value.sort.return_value.to_list = AsyncMock(return_value=[])

        result = await generate_signal("000001.SZ")

        assert result == {}

    @pytest.mark.asyncio
    @patch("trade_alpha.strategy.service.SignalResult")
    @patch("trade_alpha.strategy.service.PredictionResult.find")
    @patch("trade_alpha.strategy.service.StockDaily.find")
    async def test_generate_signal_success(self, mock_find, mock_pred_find, mock_signal_cls):
        latest = MagicMock()
        latest.trade_date = "20240101"
        latest.close = 100.0
        mock_find.return_value.sort.return_value.to_list = AsyncMock(return_value=[latest])

        pred_record = MagicMock()
        pred_record.target_open = 105.0
        pred_record.target_close = 110.0
        pred_record.target_high = 115.0
        pred_record.target_low = 95.0
        mock_pred_find.return_value.sort.return_value.first_or_none = AsyncMock(return_value=pred_record)

        mock_signal_cls.return_value.insert = AsyncMock()

        result = await generate_signal("000001.SZ")

        assert "action" in result
        assert result["action"] == "buy"
        mock_signal_cls.return_value.insert.assert_called_once()
