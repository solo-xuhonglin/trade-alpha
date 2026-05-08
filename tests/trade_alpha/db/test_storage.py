"""Unit tests for db.storage module."""

import pytest
from unittest.mock import MagicMock, patch
from trade_alpha.db.storage import Storage


class TestStorage:
    """Test cases for Storage class."""

    @patch("trade_alpha.db.storage.MongoClient")
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
        mock_collection.bulk_write.assert_called_once()

    @patch("trade_alpha.db.storage.MongoClient")
    def test_insert_many_with_modified(self, mock_client):
        mock_db = MagicMock()
        mock_client.return_value.__getitem__.return_value = mock_db
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection
        mock_result = MagicMock()
        mock_result.upserted_count = 0
        mock_result.modified_count = 2
        mock_collection.bulk_write.return_value = mock_result

        storage = Storage()
        result = storage.insert_many([
            {"ts_code": "000001.SZ", "trade_date": "20240101"},
            {"ts_code": "000001.SZ", "trade_date": "20240102"},
        ])

        assert result == 2

    def test_insert_many_empty_list(self):
        with patch("trade_alpha.db.storage.MongoClient") as mock_client:
            storage = Storage()
            result = storage.insert_many([])

            assert result == 0

    @patch("trade_alpha.db.storage.MongoClient")
    def test_find_by_ts_code(self, mock_client):
        mock_db = MagicMock()
        mock_client.return_value.__getitem__.return_value = mock_db
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection
        mock_cursor = MagicMock()
        mock_cursor.__iter__ = lambda self: iter([
            {"ts_code": "000001.SZ", "trade_date": "20240101", "close": 10.0},
            {"ts_code": "000001.SZ", "trade_date": "20240102", "close": 11.0},
        ])
        mock_collection.find.return_value.sort.return_value = mock_cursor

        storage = Storage()
        result = storage.find_by_ts_code("000001.SZ")

        assert len(result) == 2
        assert result[0]["trade_date"] == "20240101"
