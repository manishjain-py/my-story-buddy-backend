"""
Unit tests for main FastAPI application endpoints.
"""
import pytest
from unittest.mock import patch, Mock, AsyncMock
import json
from datetime import datetime
from fastapi import HTTPException
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self, test_client):
        """Test /health endpoint returns correct response."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "2.1.0"
        assert data["environment"] == "ec2"
        assert data["deployment"] == "automated-pipeline"
    
    @pytest.mark.asyncio
    async def test_ping_endpoint(self, test_client):
        """Test /ping endpoint returns pong."""
        response = test_client.get("/ping")
        assert response.status_code == 200
        assert response.json() == {"message": "pong"}


class TestStoryGeneration:
    """Test story generation endpoints."""
    
    @pytest.mark.asyncio
    async def test_generate_story_async_success(self, test_client, mock_db_manager, sample_story_request):
        """Test successful async story generation."""
        # Mock database operations
        mock_db_manager.execute_update.return_value = 1
        mock_db_manager.execute_query.return_value = [{"id": 123}]
        
        # Send request
        response = test_client.post("/generateStory", json=sample_story_request)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "IN_PROGRESS"
        assert "story_id" in data
        assert data["message"] == "Story generation started! Check My Stories for updates."
    
    @pytest.mark.asyncio
    async def test_generate_story_empty_prompt(self, test_client, mock_db_manager):
        """Test story generation with empty prompt."""
        mock_db_manager.execute_update.return_value = 1
        mock_db_manager.execute_query.return_value = [{"id": 124}]
        
        response = test_client.post("/generateStory", json={"prompt": ""})
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "IN_PROGRESS"
        assert "story_id" in data
    
    @pytest.mark.asyncio
    async def test_generate_story_duplicate_request(self, test_client, mock_db_manager, sample_story_request):
        """Test duplicate story request within cooldown period."""
        mock_db_manager.execute_update.return_value = 1
        mock_db_manager.execute_query.return_value = [{"id": 125}]
        
        # First request
        response1 = test_client.post("/generateStory", json=sample_story_request)
        assert response1.status_code == 200
        
        # Immediate duplicate request
        response2 = test_client.post("/generateStory", json=sample_story_request)
        assert response2.status_code == 429
        assert "wait a moment" in response2.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_get_story_status_success(self, test_client, mock_db_manager):
        """Test getting story status by ID."""
        # Mock story data
        mock_story = {
            "id": 123,
            "status": "NEW",
            "title": "Test Story",
            "story_content": "This is a test story.",
            "image_urls": json.dumps(["url1", "url2"]),
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        mock_db_manager.execute_query.return_value = [mock_story]
        
        response = test_client.get("/story/123/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["story_id"] == 123
        assert data["status"] == "NEW"
        assert data["title"] == "Test Story"
        assert len(data["image_urls"]) == 2
    
    @pytest.mark.asyncio
    async def test_get_story_status_not_found(self, test_client, mock_db_manager):
        """Test getting status for non-existent story."""
        mock_db_manager.execute_query.return_value = []
        
        response = test_client.get("/story/999/status")
        
        assert response.status_code == 404
        assert response.json()["detail"] == "Story not found"
    
    @pytest.mark.asyncio
    async def test_mark_story_viewed(self, test_client, mock_db_manager):
        """Test marking a story as viewed."""
        mock_db_manager.execute_update.return_value = 1
        
        response = test_client.put("/story/123/viewed")
        
        assert response.status_code == 200
        assert response.json()["message"] == "Story marked as viewed"


class TestFunFacts:
    """Test fun facts generation endpoints."""
    
    @pytest.mark.asyncio
    async def test_generate_fun_facts_success(self, test_client, mock_openai_client):
        """Test successful fun facts generation."""
        # Mock OpenAI response
        mock_content = """Q: Did you know cats can sleep for 16 hours a day?
A: Yes! Cats love to nap and dream just like us.

Q: Did you know butterflies taste with their feet?
A: Amazing! They step on flowers to see if they taste good."""
        
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = mock_content
        
        response = test_client.post("/generateFunFacts", json={"prompt": "animals"})
        
        assert response.status_code == 200
        data = response.json()
        assert "facts" in data
        assert len(data["facts"]) >= 2
        assert data["facts"][0]["question"].startswith("Did you know")
    
    @pytest.mark.asyncio
    async def test_generate_fun_facts_empty_prompt(self, test_client, mock_openai_client):
        """Test fun facts generation with empty prompt."""
        mock_content = """Q: Did you know reading stories helps your imagination grow?
A: Yes! Every story takes you on a magical adventure in your mind."""
        
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = mock_content
        
        response = test_client.post("/generateFunFacts", json={"prompt": ""})
        
        assert response.status_code == 200
        data = response.json()
        assert "facts" in data
        assert len(data["facts"]) > 0


class TestUserStories:
    """Test user stories endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_my_stories_authenticated(self, test_client, mock_db_manager, mock_jwt_utils):
        """Test getting user stories with authentication."""
        # Mock user stories
        mock_stories = [{
            "id": 1,
            "title": "User Story",
            "story_content": "Content",
            "prompt": "Prompt",
            "image_urls": json.dumps(["url1"]),
            "formats": json.dumps(["Comic Book"]),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "status": "NEW"
        }]
        mock_db_manager.execute_query.side_effect = [
            [{"id": 1, "email": "test@example.com"}],  # User lookup
            mock_stories,  # Stories
            [{"count": 1}]  # New stories count
        ]
        
        # Mock JWT verification
        with patch('main.JWTUtils') as mock_jwt_class:
            mock_jwt_class.verify_token.return_value = {"user_id": 1}
            
            response = test_client.get("/my-stories", headers={"Authorization": "Bearer test-token"})
        
        assert response.status_code == 200
        data = response.json()
        assert "stories" in data
        assert len(data["stories"]) == 1
        assert data["new_stories_count"] == 1
    
    @pytest.mark.asyncio
    async def test_get_my_stories_unauthenticated(self, test_client):
        """Test getting user stories without authentication."""
        response = test_client.get("/my-stories")
        
        assert response.status_code == 401
        assert response.json()["error"] == "Authentication required"


class TestAvatarEndpoints:
    """Test avatar-related endpoints."""
    
    @pytest.mark.asyncio
    async def test_create_avatar_success(self, test_client, mock_db_manager, mock_jwt_utils, mock_openai_client):
        """Test successful avatar creation."""
        # Mock database operations
        mock_db_manager.execute_query.side_effect = [
            [{"id": 1}],  # User exists check
            [{"id": 1, "email": "test@example.com"}],  # User lookup
        ]
        mock_db_manager.execute_update.return_value = 1
        
        # Mock avatar creation
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.lastrowid = 10
        mock_cursor.execute = AsyncMock()
        mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor
        mock_db_manager.get_connection.return_value.__aenter__.return_value = mock_conn
        
        # Mock JWT verification
        with patch('main.JWTUtils') as mock_jwt_class:
            mock_jwt_class.verify_token.return_value = {"user_id": 1}
            
            # Create multipart form data
            files = {"image": ("test.jpg", b"fake-image-data", "image/jpeg")}
            data = {
                "avatar_name": "Benny",
                "traits_description": "Brave mouse"
            }
            
            response = test_client.post(
                "/personalization/avatar",
                files=files,
                data=data,
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["avatar_name"] == "Benny"
        assert data["traits_description"] == "Brave mouse"
    
    @pytest.mark.asyncio
    async def test_get_avatar_success(self, test_client, mock_db_manager, sample_avatar_data):
        """Test getting user avatar."""
        mock_db_manager.execute_query.side_effect = [
            [{"id": 1, "email": "test@example.com"}],  # User lookup
            [sample_avatar_data]  # Avatar data
        ]
        
        with patch('main.JWTUtils') as mock_jwt_class:
            mock_jwt_class.verify_token.return_value = {"user_id": 1}
            
            response = test_client.get(
                "/personalization/avatar",
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["avatar_name"] == "Benny"
        assert data["traits_description"] == "A brave and curious mouse who loves adventures"
    
    @pytest.mark.asyncio
    async def test_update_avatar_success(self, test_client, mock_db_manager):
        """Test updating avatar details."""
        mock_db_manager.execute_query.return_value = [{"id": 1, "email": "test@example.com"}]
        mock_db_manager.execute_update.return_value = 1
        
        with patch('main.JWTUtils') as mock_jwt_class:
            mock_jwt_class.verify_token.return_value = {"user_id": 1}
            
            update_data = {
                "avatar_name": "Benny the Brave",
                "traits_description": "Even braver mouse"
            }
            
            response = test_client.put(
                "/personalization/avatar",
                json=update_data,
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["avatar_name"] == "Benny the Brave"
    
    @pytest.mark.asyncio
    async def test_create_avatar_async(self, test_client, mock_db_manager):
        """Test async avatar creation."""
        mock_db_manager.execute_query.side_effect = [
            [{"id": 1}],  # User exists
            [{"id": 1, "email": "test@example.com"}],  # User lookup
        ]
        
        # Mock avatar creation
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.lastrowid = 20
        mock_cursor.execute = AsyncMock()
        mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor
        mock_db_manager.get_connection.return_value.__aenter__.return_value = mock_conn
        
        with patch('main.JWTUtils') as mock_jwt_class:
            mock_jwt_class.verify_token.return_value = {"user_id": 1}
            
            files = {"image": ("test.jpg", b"fake-image-data", "image/jpeg")}
            data = {
                "avatar_name": "Async Benny",
                "traits_description": "Async mouse"
            }
            
            response = test_client.post(
                "/personalization/avatar/async",
                files=files,
                data=data,
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "IN_PROGRESS"
        assert "avatar_id" in data
        assert data["message"] == "Avatar generation started. Check back in a few minutes!"


class TestCORSAndPreflight:
    """Test CORS and preflight handling."""
    
    @pytest.mark.asyncio
    async def test_preflight_generate_story(self, test_client):
        """Test OPTIONS request for generateStory."""
        response = test_client.options("/generateStory")
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Methods" in response.headers
    
    @pytest.mark.asyncio
    async def test_preflight_fun_facts(self, test_client):
        """Test OPTIONS request for generateFunFacts."""
        response = test_client.options("/generateFunFacts")
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers
    
    @pytest.mark.asyncio
    async def test_preflight_my_stories(self, test_client):
        """Test OPTIONS request for my-stories."""
        response = test_client.options("/my-stories")
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers
    
    @pytest.mark.asyncio
    async def test_preflight_avatar(self, test_client):
        """Test OPTIONS request for avatar endpoints."""
        response = test_client.options("/personalization/avatar")
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Methods" in response.headers


class TestAdminEndpoints:
    """Test admin endpoints."""
    
    @pytest.mark.asyncio
    async def test_cleanup_invalid_stories(self, test_client, mock_db_manager):
        """Test cleanup of invalid stories."""
        # Mock cleanup results
        mock_db_manager.execute_query.return_value = [{"count": 5}]
        mock_db_manager.execute_update.return_value = 5
        
        response = test_client.post("/admin/cleanup-stories")
        
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 5
        assert "Successfully cleaned up 5 invalid stories" in data["message"]
    
    @pytest.mark.asyncio
    async def test_cleanup_no_invalid_stories(self, test_client, mock_db_manager):
        """Test cleanup when no invalid stories exist."""
        mock_db_manager.execute_query.return_value = [{"count": 0}]
        
        response = test_client.post("/admin/cleanup-stories")
        
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 0
        assert data["message"] == "No invalid stories found"