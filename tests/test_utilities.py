"""
Unit tests for utility functions and error handling.
"""
import pytest
from unittest.mock import patch, Mock, AsyncMock
from datetime import datetime
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
import json


class TestHelperFunctions:
    """Test helper functions from main module."""
    
    def test_cors_error_response(self):
        """Test CORS error response generation."""
        from main import cors_error_response
        
        response = cors_error_response("Test error", 400)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 400
        assert response.headers["Access-Control-Allow-Origin"] == "https://www.mystorybuddy.com"
        assert response.headers["Access-Control-Allow-Methods"] == "POST, OPTIONS"
        
        # Check body content
        body = json.loads(response.body)
        assert body["detail"] == "Test error"
    
    def test_log_request_details(self, mock_request, caplog):
        """Test request logging."""
        from main import log_request_details
        
        mock_request.method = "POST"
        mock_request.url = Mock(path="/test")
        mock_request.headers = {"Content-Type": "application/json"}
        mock_request.client = Mock(host="192.168.1.1")
        
        log_request_details(mock_request, "test-request-id")
        
        # Verify logs contain expected information
        assert "Request ID: test-request-id" in caplog.text
        assert "Request Method: POST" in caplog.text
        assert "Request Client: 192.168.1.1" in caplog.text
    
    def test_log_error(self, caplog):
        """Test error logging."""
        from main import log_error
        
        test_error = ValueError("Test error message")
        
        log_error(test_error, "test-request-id")
        
        assert "Request ID: test-request-id - Error occurred" in caplog.text
        assert "Error Type: ValueError" in caplog.text
        assert "Error Message: Test error message" in caplog.text
        assert "Traceback:" in caplog.text


class TestEmailService:
    """Test email service functionality."""
    
    @pytest.mark.asyncio
    async def test_send_welcome_email(self):
        """Test sending welcome email."""
        from core.email_service import EmailService
        
        email_service = EmailService()
        
        # Mock SMTP
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = Mock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            result = await email_service.send_welcome_email("test@example.com", "Test User")
            
            assert result is True
            mock_server.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_otp_email(self):
        """Test sending OTP email."""
        from core.email_service import EmailService
        
        email_service = EmailService()
        
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = Mock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            result = await email_service.send_otp_email("test@example.com", "123456", "Test")
            
            assert result is True
            
            # Verify email content includes OTP
            call_args = mock_server.send_message.call_args
            msg = call_args[0][0]
            assert "123456" in str(msg)
    
    @pytest.mark.asyncio
    async def test_email_service_error_handling(self):
        """Test email service error handling."""
        from core.email_service import EmailService
        
        email_service = EmailService()
        
        with patch('smtplib.SMTP') as mock_smtp:
            mock_smtp.side_effect = Exception("SMTP connection failed")
            
            # Should return False on error, not raise
            result = await email_service.send_welcome_email("test@example.com", "Test")
            
            assert result is False


class TestAuthModels:
    """Test authentication model operations."""
    
    @pytest.mark.asyncio
    async def test_user_database_create_user(self, mock_db_manager):
        """Test creating a user in database."""
        from auth.auth_models import UserDatabase, AuthType
        
        # Mock connection and cursor
        mock_cursor = AsyncMock()
        mock_cursor.lastrowid = 123
        mock_conn = AsyncMock()
        mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor
        mock_db_manager.get_connection.return_value.__aenter__.return_value = mock_conn
        
        with patch('auth.auth_models.db_manager', mock_db_manager):
            user_id = await UserDatabase.create_user(
                email="test@example.com",
                first_name="Test",
                last_name="User",
                password_hash="hashed_password",
                auth_type=AuthType.EMAIL_PASSWORD
            )
        
        assert user_id == 123
    
    @pytest.mark.asyncio
    async def test_user_database_get_user_by_email(self, mock_db_manager):
        """Test getting user by email."""
        from auth.auth_models import UserDatabase
        
        mock_user = {
            "id": 1,
            "email": "test@example.com",
            "first_name": "Test"
        }
        mock_db_manager.execute_query.return_value = [mock_user]
        
        with patch('auth.auth_models.db_manager', mock_db_manager):
            user = await UserDatabase.get_user_by_email("test@example.com")
        
        assert user == mock_user
    
    @pytest.mark.asyncio
    async def test_user_database_store_otp(self, mock_db_manager):
        """Test storing OTP."""
        from auth.auth_models import UserDatabase
        
        mock_db_manager.execute_update.return_value = 1
        
        with patch('auth.auth_models.db_manager', mock_db_manager):
            await UserDatabase.store_otp("test@example.com", "123456", expires_in_minutes=5)
        
        # Verify OTP storage query
        call_args = mock_db_manager.execute_update.call_args[0]
        assert "INSERT INTO otp_codes" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_user_database_verify_otp(self, mock_db_manager):
        """Test OTP verification."""
        from auth.auth_models import UserDatabase
        
        # Mock valid OTP
        mock_db_manager.execute_query.return_value = [{
            "otp": "123456",
            "created_at": datetime.now()
        }]
        mock_db_manager.execute_update.return_value = 1
        
        with patch('auth.auth_models.db_manager', mock_db_manager):
            is_valid = await UserDatabase.verify_otp("test@example.com", "123456")
        
        assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_user_database_create_auth_session(self, mock_db_manager):
        """Test creating authentication session."""
        from auth.auth_models import UserDatabase
        
        mock_db_manager.execute_update.return_value = 1
        
        with patch('auth.auth_models.db_manager', mock_db_manager):
            await UserDatabase.create_auth_session(
                user_id=1,
                access_token="test-token",
                expires_at=datetime.now()
            )
        
        # Verify session creation
        call_args = mock_db_manager.execute_update.call_args[0]
        assert "INSERT INTO auth_sessions" in call_args[0]


class TestGoogleAuth:
    """Test Google OAuth functionality."""
    
    @pytest.mark.asyncio
    async def test_get_google_user_info(self):
        """Test getting Google user info from token."""
        from services.google_auth import get_google_user_info
        
        mock_response = {
            "id": "google123",
            "email": "test@gmail.com",
            "name": "Test User",
            "given_name": "Test",
            "family_name": "User",
            "picture": "https://example.com/photo.jpg"
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get.return_value = Mock(
                json=lambda: mock_response,
                raise_for_status=Mock()
            )
            
            user_info = await get_google_user_info("test-access-token")
        
        assert user_info["email"] == "test@gmail.com"
        assert user_info["given_name"] == "Test"


class TestStartupShutdown:
    """Test application startup and shutdown events."""
    
    @pytest.mark.asyncio
    async def test_startup_event_success(self, mock_db_manager):
        """Test successful startup event."""
        from main import startup_event
        
        mock_db_manager.initialize = AsyncMock()
        
        with patch('main.db_manager', mock_db_manager):
            with patch('core.database.create_tables', AsyncMock()):
                with patch('auth.auth_models.UserDatabase.create_user_tables', AsyncMock()):
                    await startup_event()
        
        mock_db_manager.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_startup_event_database_failure(self, mock_db_manager):
        """Test startup with database failure."""
        from main import startup_event
        
        mock_db_manager.initialize = AsyncMock(side_effect=Exception("DB connection failed"))
        
        with patch('main.db_manager', mock_db_manager):
            # Should not raise, just log warning
            await startup_event()
    
    @pytest.mark.asyncio
    async def test_shutdown_event(self, mock_db_manager):
        """Test shutdown event."""
        from main import shutdown_event
        
        mock_db_manager.close = AsyncMock()
        
        with patch('main.db_manager', mock_db_manager):
            with patch('main.current_user', Mock()):
                await shutdown_event()
        
        mock_db_manager.close.assert_called_once()


class TestRequestDeduplication:
    """Test request deduplication logic."""
    
    @pytest.mark.asyncio
    async def test_duplicate_request_prevention(self, test_client, mock_db_manager):
        """Test that duplicate requests are prevented."""
        from main import recent_requests
        
        # Clear recent requests
        recent_requests.clear()
        
        mock_db_manager.execute_update.return_value = 1
        mock_db_manager.execute_query.return_value = [{"id": 1}]
        
        request_data = {
            "prompt": "Same story prompt",
            "formats": ["Comic Book"]
        }
        
        # First request should succeed
        response1 = test_client.post("/generateStory", json=request_data)
        assert response1.status_code == 200
        
        # Immediate duplicate should fail
        response2 = test_client.post("/generateStory", json=request_data)
        assert response2.status_code == 429
        assert "wait a moment" in response2.json()["detail"]
        
        # Clear cache and try again
        recent_requests.clear()
        response3 = test_client.post("/generateStory", json=request_data)
        assert response3.status_code == 200


class TestCatchAllRoute:
    """Test catch-all route handling."""
    
    @pytest.mark.asyncio
    async def test_catch_all_route_story(self, test_client, mock_db_manager):
        """Test catch-all route for story generation."""
        mock_db_manager.execute_update.return_value = 1
        mock_db_manager.execute_query.return_value = [{"id": 1}]
        
        response = test_client.post("/random-path", json={"prompt": "Test"})
        
        # Should default to story generation
        assert response.status_code == 200
        assert "story_id" in response.json()
    
    @pytest.mark.asyncio
    async def test_catch_all_route_fun_facts(self, test_client, mock_openai_client):
        """Test catch-all route for fun facts."""
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = (
            "Q: Test fact?\nA: Test answer."
        )
        
        response = test_client.post("/generateFunFacts", json={"prompt": "Test"})
        
        assert response.status_code == 200
        assert "facts" in response.json()