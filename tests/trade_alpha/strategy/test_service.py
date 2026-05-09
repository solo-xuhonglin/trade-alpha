"""Tests for strategy service."""

import pytest
from unittest.mock import MagicMock, patch
from trade_alpha.strategy.service import generate_signal


class TestStrategyService:
    @patch("trade_alpha.strategy.service.Storage")
    def test_generate_signal_no_data(self, mock_storage_class):
        mock_storage = MagicMock()
        mock_storage.find_by_ts_code.return_value = []
        mock_storage_class.return_value = mock_storage

        result = generate_signal("000001.SZ")

        assert result == {}
        mock_storage.close.assert_called_once()

    @patch("trade_alpha.strategy.service.Storage")
    def test_generate_signal_success(self, mock_storage_class):
        mock_storage = MagicMock()
        mock_storage.find_by_ts_code.return_value = [
            {"trade_date": "20240101", "close": 100.0},
        ]
        mock_storage._get_collection.return_value.find.return_value.sort.return_value.limit.return_value = [
            {"target_close": 110.0}
        ]
        mock_storage_class.return_value = mock_storage

        result = generate_signal("000001.SZ")

        assert "action" in result
        assert result["action"] == "buy"
        mock_storage.insert_many.assert_called_once()
        mock_storage.close.assert_called_once()
