"""Unit tests for dao.mongodb module."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestMongoDBInit:
    """Test cases for MongoDB initialization."""

    @pytest.mark.asyncio
    async def test_init_db_success(self):
        """Test successful database initialization."""
        with patch("trade_alpha.dao.mongodb.AsyncIOMotorClient") as mock_client, \
             patch("trade_alpha.dao.mongodb.init_beanie", new_callable=AsyncMock) as mock_init_beanie, \
             patch("trade_alpha.dao.mongodb.load_config") as mock_config:
            
            mock_config.return_value = MagicMock(
                mongodb_uri="mongodb://localhost:27017",
                mongodb_db="test_db"
            )
            mock_client.return_value = MagicMock()
            
            from trade_alpha.dao.mongodb import init_db
            
            await init_db()
            
            mock_client.assert_called_once_with("mongodb://localhost:27017")
            mock_init_beanie.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_db(self):
        """Test closing database connection."""
        with patch("trade_alpha.dao.mongodb._db_client") as mock_client:
            from trade_alpha.dao.mongodb import close_db
            
            import trade_alpha.dao.mongodb as db_module
            db_module._db_client = MagicMock()
            
            await close_db()
            
            assert db_module._db_client is None

    def test_get_db_returns_client(self):
        """Test get_db returns the client."""
        import trade_alpha.dao.mongodb as db_module
        from trade_alpha.dao.mongodb import get_db
        
        mock_client = MagicMock()
        db_module._db_client = mock_client
        
        result = get_db()
        
        assert result == mock_client

    def test_get_db_returns_none_when_not_initialized(self):
        """Test get_db returns None when not initialized."""
        import trade_alpha.dao.mongodb as db_module
        from trade_alpha.dao.mongodb import get_db
        
        db_module._db_client = None
        
        result = get_db()
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_database_returns_db_instance(self):
        """Test get_database returns database instance."""
        with patch("trade_alpha.dao.mongodb._db_client") as mock_client, \
             patch("trade_alpha.dao.mongodb.load_config") as mock_config:
            
            mock_config.return_value = MagicMock(mongodb_db="test_db")
            mock_db = MagicMock()
            mock_client.__getitem__ = MagicMock(return_value=mock_db)
            
            import trade_alpha.dao.mongodb as db_module
            db_module._db_client = mock_client
            
            from trade_alpha.dao.mongodb import get_database
            
            result = await get_database()
            
            assert result is not None

    @pytest.mark.asyncio
    async def test_get_database_returns_none_when_not_initialized(self):
        """Test get_database returns None when not initialized."""
        import trade_alpha.dao.mongodb as db_module
        db_module._db_client = None
        
        from trade_alpha.dao.mongodb import get_database
        
        result = await get_database()
        
        assert result is None
