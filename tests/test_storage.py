"""Tests for storage module."""

import pytest
from unittest.mock import MagicMock, patch
from data.storage import Storage


class TestStorage:
    """Test cases for Storage class."""

    @patch("data.storage.MongoClient")
    def test_insert_many_returns_count(self, mock_client):
        mock_db = MagicMock()
        mock_client.return_value.__getitem__.return_value = mock_db
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection
        mock_collection.insert_many.return_value = MagicMock()

        storage = Storage()
        result = storage.insert_many([{"ts_code": "000001.SZ", "trade_date": "20240101"}])

        assert result == 1
        mock_collection.insert_many.assert_called_once()

    @patch("data.storage.MongoClient")
    def test_insert_many_with_upsert(self, mock_client):
        mock_db = MagicMock()
        mock_client.return_value.__getitem__.return_value = mock_db
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection
        mock_result = MagicMock()
        mock_result.upserted_count = 1
        mock_result.modified_count = 0
        mock_collection.bulk_write.return_value = mock_result

        storage = Storage()
        result = storage.insert_many([{"ts_code": "000001.SZ", "trade_date": "20240101"}])

        assert result == 1

    @patch("data.storage.MongoClient")
    def test_insert_many_empty_list(self, mock_client):
        storage = Storage()
        result = storage.insert_many([])

        assert result == 0
        mock_client.assert_not_called()
