"""
Unit tests for database operations.
"""
import pytest
from unittest.mock import patch, Mock, AsyncMock, MagicMock
import json
from datetime import datetime
import aiomysql


class TestDatabaseManager:
    """Test DatabaseManager class."""
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, mock_db_manager):
        """Test successful database initialization."""
        from core.database import DatabaseManager
        
        db_manager = DatabaseManager()
        
        with patch('aiomysql.create_pool', AsyncMock(return_value=Mock())):
            await db_manager.initialize()
            
        assert db_manager.pool is not None
    
    @pytest.mark.asyncio
    async def test_initialize_failure(self):
        """Test database initialization failure."""
        from core.database import DatabaseManager
        
        db_manager = DatabaseManager()
        
        with patch('aiomysql.create_pool', AsyncMock(side_effect=Exception("Connection failed"))):
            # Should not raise, just log error
            await db_manager.initialize()
            
        assert db_manager.pool is None
    
    @pytest.mark.asyncio
    async def test_test_connection(self, mock_db_manager):
        """Test database connectivity test."""
        # Configure mock connection
        mock_cursor = AsyncMock()
        mock_cursor.execute = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(1,))
        
        mock_conn = AsyncMock()
        mock_conn.cursor = AsyncMock(return_value=mock_cursor)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        
        mock_pool = Mock()
        mock_pool.acquire = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
        
        mock_db_manager.pool = mock_pool
        
        await mock_db_manager.test_connection()
        
        mock_cursor.execute.assert_called_with("SELECT 1 as test")
    
    @pytest.mark.asyncio
    async def test_execute_query(self, mock_db_manager):
        """Test executing SELECT query."""
        expected_results = [{"id": 1, "title": "Test Story"}]
        mock_db_manager.execute_query.return_value = expected_results
        
        results = await mock_db_manager.execute_query("SELECT * FROM stories WHERE id = %s", (1,))
        
        assert results == expected_results
        mock_db_manager.execute_query.assert_called_with("SELECT * FROM stories WHERE id = %s", (1,))
    
    @pytest.mark.asyncio
    async def test_execute_update(self, mock_db_manager):
        """Test executing INSERT/UPDATE query."""
        mock_db_manager.execute_update.return_value = 1
        
        affected_rows = await mock_db_manager.execute_update(
            "UPDATE stories SET status = %s WHERE id = %s",
            ("VIEWED", 1)
        )
        
        assert affected_rows == 1
    
    @pytest.mark.asyncio
    async def test_reconnect(self):
        """Test database reconnection."""
        from core.database import DatabaseManager
        
        db_manager = DatabaseManager()
        db_manager.close = AsyncMock()
        db_manager.initialize = AsyncMock()
        
        await db_manager.reconnect()
        
        db_manager.close.assert_called_once()
        db_manager.initialize.assert_called_once()


class TestStoryOperations:
    """Test story-related database operations."""
    
    @pytest.mark.asyncio
    async def test_save_story(self, mock_db_manager):
        """Test saving a story to database."""
        from core.database import save_story
        
        mock_db_manager.execute_update.return_value = 1
        mock_db_manager.execute_query.return_value = [{"id": 123}]
        
        # Patch the module-level db_manager
        with patch('core.database.db_manager', mock_db_manager):
            story_id = await save_story(
                title="Test Story",
                story_content="Once upon a time...",
                prompt="Tell me a story",
                image_urls=["url1", "url2"],
                formats=["Comic Book"],
                request_id="test-request",
                user_id="1",
                status="NEW"
            )
        
        assert story_id == 123
        
        # Verify query was called with correct parameters
        call_args = mock_db_manager.execute_update.call_args[0]
        assert "INSERT INTO stories" in call_args[0]
        params = call_args[1]
        assert params[0] == "Test Story"
        assert params[1] == "Once upon a time..."
        assert json.loads(params[3]) == ["url1", "url2"]
    
    @pytest.mark.asyncio
    async def test_create_story_placeholder(self, mock_db_manager):
        """Test creating story placeholder."""
        from core.database import create_story_placeholder
        
        mock_db_manager.execute_update.return_value = 1
        mock_db_manager.execute_query.return_value = [{"id": 456}]
        
        with patch('core.database.db_manager', mock_db_manager):
            story_id = await create_story_placeholder(
                prompt="Test prompt",
                formats=["Comic Book"],
                request_id="test-req",
                user_id="1"
            )
        
        assert story_id == 456
        
        # Verify placeholder values
        call_args = mock_db_manager.execute_update.call_args[0]
        params = call_args[1]
        assert params[0] == "Story in Progress..."
        assert params[1] == "Your story is being generated..."
        assert params[7] == "IN_PROGRESS"
    
    @pytest.mark.asyncio
    async def test_update_story_content(self, mock_db_manager):
        """Test updating story content."""
        from core.database import update_story_content
        
        mock_db_manager.execute_update.return_value = 1
        
        with patch('core.database.db_manager', mock_db_manager):
            success = await update_story_content(
                story_id=123,
                title="Updated Title",
                story_content="Updated content",
                image_urls=["new_url1", "new_url2"],
                status="NEW"
            )
        
        assert success is True
        
        # Verify update query
        call_args = mock_db_manager.execute_update.call_args[0]
        assert "UPDATE stories" in call_args[0]
        params = call_args[1]
        assert params[0] == "Updated Title"
        assert params[4] == 123
    
    @pytest.mark.asyncio
    async def test_update_story_status(self, mock_db_manager):
        """Test updating story status."""
        from core.database import update_story_status
        
        mock_db_manager.execute_update.return_value = 1
        
        with patch('core.database.db_manager', mock_db_manager):
            success = await update_story_status(123, "VIEWED")
        
        assert success is True
        call_args = mock_db_manager.execute_update.call_args[0]
        assert "UPDATE stories" in call_args[0]
        assert "status = %s" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_get_story_by_id(self, mock_db_manager):
        """Test getting story by ID."""
        from core.database import get_story_by_id
        
        mock_story = {
            "id": 123,
            "title": "Test Story",
            "story_content": "Content",
            "image_urls": '["url1", "url2"]',
            "formats": '["Comic Book"]',
            "status": "NEW"
        }
        mock_db_manager.execute_query.return_value = [mock_story]
        
        with patch('core.database.db_manager', mock_db_manager):
            story = await get_story_by_id(123)
        
        assert story is not None
        assert story["id"] == 123
        assert story["image_urls"] == ["url1", "url2"]
        assert story["formats"] == ["Comic Book"]
    
    @pytest.mark.asyncio
    async def test_get_recent_stories(self, mock_db_manager):
        """Test getting recent stories."""
        from core.database import get_recent_stories
        
        mock_stories = [
            {
                "id": 1,
                "title": "Story 1",
                "image_urls": '["url1"]',
                "formats": '["Comic Book"]'
            },
            {
                "id": 2,
                "title": "Story 2",
                "image_urls": None,
                "formats": None
            }
        ]
        mock_db_manager.execute_query.return_value = mock_stories
        
        with patch('core.database.db_manager', mock_db_manager):
            stories = await get_recent_stories(limit=10, user_id="1")
        
        assert len(stories) == 2
        assert stories[0]["image_urls"] == ["url1"]
        assert stories[1]["image_urls"] is None
    
    @pytest.mark.asyncio
    async def test_get_new_stories_count(self, mock_db_manager):
        """Test getting count of new stories."""
        from core.database import get_new_stories_count
        
        mock_db_manager.execute_query.return_value = [{"count": 5}]
        
        with patch('core.database.db_manager', mock_db_manager):
            count = await get_new_stories_count(user_id="1")
        
        assert count == 5
    
    @pytest.mark.asyncio
    async def test_cleanup_invalid_stories(self, mock_db_manager):
        """Test cleanup of invalid stories."""
        from core.database import cleanup_invalid_stories
        
        mock_db_manager.execute_query.return_value = [{"count": 10}]
        mock_db_manager.execute_update.return_value = 10
        
        with patch('core.database.db_manager', mock_db_manager):
            result = await cleanup_invalid_stories()
        
        assert result["deleted_count"] == 10
        assert "Successfully cleaned up 10" in result["message"]


class TestAvatarOperations:
    """Test avatar-related database operations."""
    
    @pytest.mark.asyncio
    async def test_create_user_avatar(self, mock_db_manager):
        """Test creating user avatar."""
        from core.database import create_user_avatar
        
        # Mock user exists check
        mock_db_manager.execute_query.return_value = [{"id": 1}]
        mock_db_manager.execute_update.return_value = 1
        
        # Mock connection and cursor for direct database access
        mock_cursor = AsyncMock()
        mock_cursor.lastrowid = 999
        mock_cursor.execute = AsyncMock()
        mock_cursor.rowcount = 1
        
        mock_conn = AsyncMock()
        mock_conn.cursor = Mock()
        mock_conn.cursor.return_value.__aenter__ = AsyncMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Set up the get_connection context manager properly
        mock_connection_cm = AsyncMock()
        mock_connection_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_connection_cm.__aexit__ = AsyncMock(return_value=None)
        mock_db_manager.get_connection = Mock(return_value=mock_connection_cm)
        
        with patch('core.database.db_manager', mock_db_manager):
            avatar_id = await create_user_avatar(
                user_id=1,
                avatar_name="TestAvatar",
                traits_description="Test traits",
                s3_image_url="https://s3/avatar.png",
                visual_traits="Visual description"
            )
        
        assert avatar_id == 999
    
    @pytest.mark.asyncio
    async def test_get_user_avatar(self, mock_db_manager):
        """Test getting user avatar."""
        from core.database import get_user_avatar
        
        mock_avatar = {
            "id": 1,
            "avatar_name": "Benny",
            "traits_description": "Brave mouse",
            "s3_image_url": "https://s3/avatar.png",
            "visual_traits": "Brown mouse",
            "status": "COMPLETED"
        }
        mock_db_manager.execute_query.return_value = [mock_avatar]
        
        with patch('core.database.db_manager', mock_db_manager):
            avatar = await get_user_avatar(user_id=1)
        
        assert avatar is not None
        assert avatar["avatar_name"] == "Benny"
        assert avatar["visual_traits"] == "Brown mouse"
    
    @pytest.mark.asyncio
    async def test_update_user_avatar(self, mock_db_manager):
        """Test updating user avatar."""
        from core.database import update_user_avatar
        
        mock_db_manager.execute_update.return_value = 1
        
        with patch('core.database.db_manager', mock_db_manager):
            success = await update_user_avatar(
                user_id=1,
                avatar_name="Updated Name",
                traits_description="Updated traits"
            )
        
        assert success is True
        
        # Verify update query
        call_args = mock_db_manager.execute_update.call_args[0]
        assert "UPDATE user_avatars" in call_args[0]
        assert "avatar_name = %s" in call_args[0]
        assert "traits_description = %s" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_update_avatar_status_with_traits(self, mock_db_manager):
        """Test updating avatar status with visual traits."""
        from core.database import update_avatar_status_with_traits
        
        mock_db_manager.execute_update.return_value = 1
        
        with patch('core.database.db_manager', mock_db_manager):
            success = await update_avatar_status_with_traits(
                avatar_id=1,
                status="COMPLETED",
                s3_image_url="https://s3/new-avatar.png",
                visual_traits="New visual traits"
            )
        
        assert success is True
        
        # Verify all fields are updated
        call_args = mock_db_manager.execute_update.call_args[0]
        assert "status = %s" in call_args[0]
        assert "s3_image_url = %s" in call_args[0]
        assert "visual_traits = %s" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_get_completed_avatars_count(self, mock_db_manager):
        """Test getting count of completed avatars."""
        from core.database import get_completed_avatars_count
        
        mock_db_manager.execute_query.return_value = [{"count": 3}]
        
        with patch('core.database.db_manager', mock_db_manager):
            count = await get_completed_avatars_count(user_id=1)
        
        assert count == 3


class TestFunFactsOperations:
    """Test fun facts database operations."""
    
    @pytest.mark.asyncio
    async def test_save_fun_facts(self, mock_db_manager):
        """Test saving fun facts."""
        from core.database import save_fun_facts
        
        mock_db_manager.execute_update.return_value = 1
        mock_db_manager.execute_query.return_value = [{"id": 789}]
        
        facts = [
            {"question": "Did you know?", "answer": "Yes!"},
            {"question": "Another fact?", "answer": "Indeed!"}
        ]
        
        with patch('core.database.db_manager', mock_db_manager):
            fact_id = await save_fun_facts(
                prompt="Tell me fun facts",
                facts=facts,
                request_id="test-req"
            )
        
        assert fact_id == 789
        
        # Verify JSON serialization
        call_args = mock_db_manager.execute_update.call_args[0]
        params = call_args[1]
        assert json.loads(params[1]) == facts


class TestDatabaseMigrations:
    """Test database migration functions."""
    
    @pytest.mark.asyncio
    async def test_create_tables(self, mock_db_manager):
        """Test table creation."""
        from core.database import create_tables
        
        mock_db_manager.execute_update.return_value = 1
        
        with patch('core.database.run_migrations', AsyncMock()):
            with patch('core.database.db_manager', mock_db_manager):
                await create_tables()
        
        # Verify all tables are created
        calls = mock_db_manager.execute_update.call_args_list
        assert len(calls) >= 4  # stories, fun_facts, user_sessions, user_avatars
        
        # Check for specific table creation
        all_queries = " ".join([call[0][0] for call in calls])
        assert "CREATE TABLE IF NOT EXISTS stories" in all_queries
        assert "CREATE TABLE IF NOT EXISTS fun_facts" in all_queries
        assert "CREATE TABLE IF NOT EXISTS user_sessions" in all_queries
        assert "CREATE TABLE IF NOT EXISTS user_avatars" in all_queries
    
    @pytest.mark.asyncio
    async def test_run_migrations(self, mock_db_manager):
        """Test running database migrations."""
        from core.database import run_migrations
        
        # Mock migration success and duplicate column errors
        mock_db_manager.execute_update.side_effect = [
            Exception("Duplicate column name 'status'"),  # Already exists
            Exception("Duplicate key name 'idx_status'"),  # Index exists
            1,  # New migration succeeds
            1   # Another succeeds
        ]
        
        # Should not raise exceptions for duplicate columns/indexes
        with patch('core.database.db_manager', mock_db_manager):
            await run_migrations()
        
        # Verify migration attempts
        assert mock_db_manager.execute_update.call_count >= 4