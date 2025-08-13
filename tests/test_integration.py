"""
Integration tests for complete workflows.
"""
import pytest
from unittest.mock import patch, Mock, AsyncMock
import json
import time
from datetime import datetime
from fastapi.testclient import TestClient


class TestStoryGenerationWorkflow:
    """Test complete story generation workflow."""
    
    @pytest.mark.asyncio
    async def test_complete_story_generation_workflow(self, test_client, mock_db_manager, mock_openai_client):
        """Test end-to-end story generation workflow."""
        # Mock database operations for story creation
        mock_db_manager.execute_update.return_value = 1
        mock_db_manager.execute_query.side_effect = [
            [{"id": 1}],  # Story placeholder creation
            [{  # Story status check
                "id": 1,
                "status": "NEW",
                "title": "The Brave Mouse",
                "story_content": "Once upon a time...\n\nThe End! (Created By - MyStoryBuddy)",
                "image_urls": json.dumps([
                    "https://s3.amazonaws.com/image1.png",
                    "https://s3.amazonaws.com/image2.png",
                    "https://s3.amazonaws.com/image3.png",
                    "https://s3.amazonaws.com/image4.png"
                ]),
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }]
        ]
        
        # Mock OpenAI story generation
        story_content = "Title: The Brave Mouse\n\nOnce upon a time, there was a brave little mouse...\n\nThe End! (Created By - MyStoryBuddy)"
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = story_content
        
        # Mock OpenAI image generation
        mock_openai_client.images.generate.return_value.data = [Mock(b64_json="base64imagedata")]
        
        # Step 1: Submit story request
        story_request = {
            "prompt": "A story about a brave little mouse",
            "formats": ["Comic Book", "Text Story"]
        }
        
        with patch('main.save_image_to_s3', AsyncMock(return_value="https://s3.amazonaws.com/image.png")):
            with patch('core.database.update_story_content', AsyncMock(return_value=True)):
                response = test_client.post("/generateStory", json=story_request)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "IN_PROGRESS"
        story_id = data["story_id"]
        
        # Step 2: Check story status (simulate background completion)
        response = test_client.get(f"/story/{story_id}/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["story_id"] == story_id
        assert data["status"] == "NEW"
        assert data["title"] == "The Brave Mouse"
        assert len(data["image_urls"]) == 4
        
        # Step 3: Mark story as viewed
        response = test_client.put(f"/story/{story_id}/viewed")
        
        assert response.status_code == 200
        assert "marked as viewed" in response.json()["message"]
    
    @pytest.mark.asyncio
    async def test_story_generation_with_avatar_workflow(self, test_client, mock_db_manager, mock_openai_client):
        """Test story generation workflow with user avatar integration."""
        # Mock user authentication
        mock_db_manager.execute_query.side_effect = [
            [{"id": 1, "email": "test@example.com"}],  # User lookup
            [{"id": 1}],  # Story placeholder creation
            [{  # Avatar data for enrichment
                "avatar_name": "Benny",
                "traits_description": "A brave and curious mouse",
                "visual_traits": "Small brown mouse with big ears"
            }]
        ]
        mock_db_manager.execute_update.return_value = 1
        
        # Mock story generation with avatar enrichment
        enriched_story = "Title: Benny's Adventure\n\nBenny the brave mouse went on an adventure...\n\nThe End! (Created By - MyStoryBuddy)"
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = enriched_story
        
        with patch('main.JWTUtils') as mock_jwt:
            mock_jwt.verify_token.return_value = {"user_id": 1}
            
            with patch('main.save_image_to_s3', AsyncMock(return_value="https://s3.amazonaws.com/image.png")):
                with patch('core.database.update_story_content', AsyncMock(return_value=True)):
                    story_request = {
                        "prompt": "Tell me a story about Benny the mouse",
                        "formats": ["Comic Book"]
                    }
                    
                    response = test_client.post(
                        "/generateStory",
                        json=story_request,
                        headers={"Authorization": "Bearer test-token"}
                    )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "IN_PROGRESS"
        assert "story_id" in data


class TestUserAuthenticationWorkflow:
    """Test complete user authentication workflows."""
    
    @pytest.mark.asyncio
    async def test_user_signup_login_workflow(self, test_client, mock_db_manager, mock_email_service):
        """Test complete user signup and login workflow."""
        # Step 1: User signup
        mock_db_manager.execute_query.side_effect = [
            [],  # No existing user
            [{"id": 1, "email": "newuser@example.com", "first_name": "New"}]  # Created user
        ]
        
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.lastrowid = 1
        mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor
        mock_db_manager.get_connection.return_value.__aenter__.return_value = mock_conn
        
        with patch('auth.auth_models.db_manager', mock_db_manager):
            with patch('core.email_service.email_service', mock_email_service):
                signup_data = {
                    "email": "newuser@example.com",
                    "password": "SecurePass123!",
                    "first_name": "New",
                    "last_name": "User"
                }
                
                response = test_client.post("/auth/signup", json=signup_data)
        
        assert response.status_code == 201
        signup_response = response.json()
        assert "access_token" in signup_response
        
        # Step 2: User login with same credentials
        user_data = {
            "id": 1,
            "email": "newuser@example.com",
            "first_name": "New",
            "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiGpO6EsjO7y"  # SecurePass123!
        }
        mock_db_manager.execute_query.return_value = [user_data]
        
        with patch('auth.auth_models.db_manager', mock_db_manager):
            login_data = {
                "email": "newuser@example.com",
                "password": "SecurePass123!"
            }
            
            response = test_client.post("/auth/login", json=login_data)
        
        assert response.status_code == 200
        login_response = response.json()
        assert "access_token" in login_response
        
        # Step 3: Access protected endpoint
        with patch('auth.auth_models.db_manager', mock_db_manager):
            with patch('auth.auth_utils.JWTUtils.verify_token', return_value={"user_id": 1}):
                response = test_client.get(
                    "/auth/me",
                    headers={"Authorization": f"Bearer {login_response['access_token']}"}
                )
        
        assert response.status_code == 200
        user_info = response.json()
        assert user_info["email"] == "newuser@example.com"
    
    @pytest.mark.asyncio
    async def test_otp_authentication_workflow(self, test_client, mock_db_manager, mock_email_service):
        """Test OTP-based authentication workflow."""
        # Step 1: Send OTP
        mock_db_manager.execute_query.return_value = [{"first_name": "Test"}]
        mock_db_manager.execute_update.return_value = 1
        
        with patch('auth.auth_models.db_manager', mock_db_manager):
            with patch('core.email_service.email_service', mock_email_service):
                response = test_client.post("/auth/send-otp", json={"email": "test@example.com"})
        
        assert response.status_code == 200
        assert "OTP sent" in response.json()["message"]
        
        # Step 2: Verify OTP
        mock_db_manager.execute_query.side_effect = [
            [{"otp": "123456", "created_at": datetime.now()}],  # Valid OTP
            [{"id": 1, "email": "test@example.com"}]  # Existing user
        ]
        
        with patch('auth.auth_models.db_manager', mock_db_manager):
            otp_data = {
                "email": "test@example.com",
                "otp": "123456"
            }
            
            response = test_client.post("/auth/verify-otp", json=otp_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        
        # Step 3: Logout
        mock_db_manager.execute_update.return_value = 1
        
        with patch('auth.auth_models.db_manager', mock_db_manager):
            response = test_client.post(
                "/auth/logout",
                headers={"Authorization": f"Bearer {data['access_token']}"}
            )
        
        assert response.status_code == 200
        assert "Logged out successfully" in response.json()["message"]


class TestAvatarCreationWorkflow:
    """Test complete avatar creation and usage workflow."""
    
    @pytest.mark.asyncio
    async def test_avatar_creation_and_story_generation_workflow(self, test_client, mock_db_manager, mock_openai_client):
        """Test creating avatar and using it in story generation."""
        # Mock user authentication
        mock_db_manager.execute_query.side_effect = [
            [{"id": 1}],  # User exists check
            [{"id": 1, "email": "test@example.com"}],  # User lookup for avatar creation
            [{  # Avatar data after creation
                "id": 1,
                "avatar_name": "Benny",
                "traits_description": "Brave mouse",
                "s3_image_url": "https://s3/avatar.png",
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }],
            [{"id": 1, "email": "test@example.com"}],  # User lookup for story
            [{"id": 1}],  # Story placeholder
            [{  # Avatar data for story enrichment
                "avatar_name": "Benny",
                "traits_description": "Brave mouse",
                "visual_traits": "Brown mouse with big ears"
            }]
        ]
        
        # Mock avatar creation
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.lastrowid = 1
        mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor
        mock_db_manager.get_connection.return_value.__aenter__.return_value = mock_conn
        mock_db_manager.execute_update.return_value = 1
        
        # Mock OpenAI for avatar generation
        mock_openai_client.chat.completions.create.side_effect = [
            Mock(choices=[Mock(message=Mock(content="Character description"))]),
            Mock(choices=[Mock(message=Mock(content="Visual traits"))])
        ]
        mock_openai_client.images.generate.return_value = Mock(data=[Mock(b64_json="avatardata")])
        
        with patch('main.JWTUtils') as mock_jwt:
            mock_jwt.verify_token.return_value = {"user_id": 1}
            
            # Step 1: Create avatar
            with patch('main.save_avatar_to_s3', AsyncMock(return_value="https://s3/avatar.png")):
                files = {"image": ("avatar.jpg", b"fake-image-data", "image/jpeg")}
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
            avatar_data = response.json()
            assert avatar_data["avatar_name"] == "Benny"
            
            # Step 2: Generate story using avatar
            story_content = "Title: Benny's Adventure\n\nBenny the brave mouse...\n\nThe End! (Created By - MyStoryBuddy)"
            mock_openai_client.chat.completions.create.return_value.choices[0].message.content = story_content
            
            with patch('main.save_image_to_s3', AsyncMock(return_value="https://s3/story-image.png")):
                with patch('core.database.update_story_content', AsyncMock(return_value=True)):
                    story_request = {
                        "prompt": "Tell me a story about Benny going on an adventure",
                        "formats": ["Comic Book"]
                    }
                    
                    response = test_client.post(
                        "/generateStory",
                        json=story_request,
                        headers={"Authorization": "Bearer test-token"}
                    )
            
            assert response.status_code == 200
            story_response = response.json()
            assert story_response["status"] == "IN_PROGRESS"
    
    @pytest.mark.asyncio
    async def test_avatar_async_creation_workflow(self, test_client, mock_db_manager, mock_openai_client):
        """Test async avatar creation workflow."""
        # Mock user authentication
        mock_db_manager.execute_query.side_effect = [
            [{"id": 1}],  # User exists
            [{"id": 1, "email": "test@example.com"}],  # User lookup
            [{  # Avatar status check
                "id": 1,
                "status": "COMPLETED",
                "avatar_name": "Async Benny",
                "traits_description": "Async mouse",
                "s3_image_url": "https://s3/async-avatar.png",
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }]
        ]
        
        # Mock avatar creation
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.lastrowid = 1
        mock_conn.cursor.return_value.__aenter__.return_value = mock_cursor
        mock_db_manager.get_connection.return_value.__aenter__.return_value = mock_conn
        
        with patch('main.JWTUtils') as mock_jwt:
            mock_jwt.verify_token.return_value = {"user_id": 1}
            
            # Step 1: Start async avatar creation
            files = {"image": ("avatar.jpg", b"fake-image-data", "image/jpeg")}
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
            async_response = response.json()
            assert async_response["status"] == "IN_PROGRESS"
            avatar_id = async_response["avatar_id"]
            
            # Step 2: Check avatar status (simulate completion)
            response = test_client.get(
                f"/personalization/avatar/status/{avatar_id}",
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == 200
            status_data = response.json()
            assert status_data["status"] == "COMPLETED"
            assert status_data["avatar_name"] == "Async Benny"


class TestErrorHandlingWorkflows:
    """Test error handling in complete workflows."""
    
    @pytest.mark.asyncio
    async def test_story_generation_failure_workflow(self, test_client, mock_db_manager, mock_openai_client):
        """Test story generation workflow when OpenAI fails."""
        # Mock database for placeholder creation
        mock_db_manager.execute_update.return_value = 1
        mock_db_manager.execute_query.return_value = [{"id": 1}]
        
        # Mock OpenAI failure
        mock_openai_client.chat.completions.create.side_effect = Exception("OpenAI API Error")
        
        with patch('core.database.update_story_content', AsyncMock(return_value=True)) as mock_update:
            story_request = {
                "prompt": "A story that will fail to generate",
                "formats": ["Comic Book"]
            }
            
            response = test_client.post("/generateStory", json=story_request)
            
            # Should still return 200 with IN_PROGRESS status
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "IN_PROGRESS"
            
            # Background task should update with error story
            # Verify error story was saved
            mock_update.assert_called_with(
                1,
                "Story Generation Failed",
                "We encountered an error while generating your story. Please try again.",
                [],
                status='NEW'
            )
    
    @pytest.mark.asyncio
    async def test_authentication_failure_workflow(self, test_client, mock_db_manager):
        """Test workflows when authentication fails."""
        # Test accessing protected endpoint without token
        response = test_client.get("/my-stories")
        assert response.status_code == 401
        assert "Authentication required" in response.json()["error"]
        
        # Test with invalid token
        with patch('main.JWTUtils') as mock_jwt:
            mock_jwt.verify_token.return_value = None
            
            response = test_client.get(
                "/my-stories",
                headers={"Authorization": "Bearer invalid-token"}
            )
            
            assert response.status_code == 401
            assert "Invalid token" in response.json()["error"]
    
    @pytest.mark.asyncio
    async def test_database_failure_workflow(self, test_client, mock_db_manager):
        """Test workflows when database operations fail."""
        # Mock database failure
        mock_db_manager.execute_update.side_effect = Exception("Database connection lost")
        
        story_request = {
            "prompt": "Test story",
            "formats": ["Comic Book"]
        }
        
        response = test_client.post("/generateStory", json=story_request)
        
        # Should return error response
        assert response.status_code == 500
        assert "detail" in response.json()


class TestFunFactsWorkflow:
    """Test fun facts generation workflow."""
    
    @pytest.mark.asyncio
    async def test_fun_facts_generation_workflow(self, test_client, mock_openai_client, mock_db_manager):
        """Test complete fun facts generation workflow."""
        # Mock OpenAI response
        facts_content = """Q: Did you know cats can sleep for 16 hours a day?
A: Yes! Cats love to nap and dream just like us.

Q: Did you know butterflies taste with their feet?
A: Amazing! They step on flowers to see if they taste good."""
        
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = facts_content
        mock_db_manager.execute_update.return_value = 1
        mock_db_manager.execute_query.return_value = [{"id": 1}]
        
        # Generate fun facts
        response = test_client.post("/generateFunFacts", json={"prompt": "animals"})
        
        assert response.status_code == 200
        data = response.json()
        assert "facts" in data
        assert len(data["facts"]) >= 2
        
        # Verify fact structure
        fact = data["facts"][0]
        assert "question" in fact
        assert "answer" in fact
        assert fact["question"].startswith("Did you know")
        
        # Test with empty prompt
        response = test_client.post("/generateFunFacts", json={"prompt": ""})
        
        assert response.status_code == 200
        data = response.json()
        assert "facts" in data