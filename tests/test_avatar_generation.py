"""
Unit tests for image generation and avatar functionality.
"""
import pytest
from unittest.mock import patch, Mock, AsyncMock, MagicMock
import base64
import json
from datetime import datetime
from io import BytesIO


class TestImageGeneration:
    """Test image generation functions."""
    
    @pytest.mark.asyncio
    async def test_save_image_to_s3_success(self, mock_s3_client):
        """Test successful image upload to S3."""
        from main import save_image_to_s3
        
        # Mock successful S3 upload
        mock_s3_client.put_object = Mock(return_value={'ETag': '"test-etag"'})
        
        with patch('main.s3_client', mock_s3_client):
            with patch('asyncio.to_thread', AsyncMock(return_value=None)):
                result = await save_image_to_s3(
                    image_bytes=b"fake-image-data",
                    content_type="image/png",
                    request_id="test-request-id",
                    image_index=1
                )
        
        assert result.startswith("https://mystorybuddy-assets.s3.amazonaws.com/")
        assert "test-request-id_image_1.png" in result
    
    @pytest.mark.asyncio
    async def test_save_image_to_s3_no_client(self):
        """Test image upload when S3 client is not initialized."""
        from main import save_image_to_s3
        
        with patch('main.s3_client', None):
            result = await save_image_to_s3(
                image_bytes=b"fake-image-data",
                request_id="test-request-id"
            )
        
        assert result == "https://via.placeholder.com/400x300?text=Image+Upload+Disabled"
    
    @pytest.mark.asyncio
    async def test_save_image_to_s3_no_data(self, mock_s3_client):
        """Test image upload with no image data."""
        from main import save_image_to_s3
        
        with patch('main.s3_client', mock_s3_client):
            result = await save_image_to_s3(
                image_bytes=b"",
                request_id="test-request-id"
            )
        
        assert result == "https://via.placeholder.com/400x300?text=No+Image+Data"
    
    @pytest.mark.asyncio
    async def test_save_image_to_s3_error(self, mock_s3_client):
        """Test error handling during S3 upload."""
        from main import save_image_to_s3
        from botocore.exceptions import NoCredentialsError
        from fastapi import HTTPException
        
        # Mock S3 error
        mock_s3_client.put_object = Mock(side_effect=NoCredentialsError())
        
        with patch('main.s3_client', mock_s3_client):
            with patch('asyncio.to_thread', AsyncMock(side_effect=NoCredentialsError())):
                with pytest.raises(HTTPException) as exc_info:
                    await save_image_to_s3(
                        image_bytes=b"fake-image-data",
                        request_id="test-request-id"
                    )
        
        assert exc_info.value.status_code == 500
        assert "AWS credentials not configured" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_save_avatar_to_s3_success(self, mock_s3_client):
        """Test successful avatar upload to S3."""
        from main import save_avatar_to_s3
        
        mock_s3_client.put_object = Mock(return_value={'ETag': '"test-etag"'})
        
        with patch('main.s3_client', mock_s3_client):
            with patch('asyncio.to_thread', AsyncMock(return_value=None)):
                result = await save_avatar_to_s3(
                    image_bytes=b"avatar-image-data",
                    user_id=123,
                    request_id="test-request-id"
                )
        
        assert result.startswith("https://mystorybuddy-assets.s3.amazonaws.com/avatars/")
        assert "user_123_test-request-id.png" in result
    
    @pytest.mark.asyncio
    async def test_save_avatar_to_s3_no_client(self):
        """Test avatar upload when S3 client is not initialized."""
        from main import save_avatar_to_s3
        from fastapi import HTTPException
        
        with patch('main.s3_client', None):
            with pytest.raises(HTTPException) as exc_info:
                await save_avatar_to_s3(
                    image_bytes=b"avatar-data",
                    user_id=1,
                    request_id="test-id"
                )
        
        assert exc_info.value.status_code == 500
        assert "Image storage not available" in str(exc_info.value.detail)


class TestAvatarGeneration:
    """Test avatar generation and processing."""
    
    @pytest.mark.asyncio
    async def test_create_comic_avatar_and_extract_traits_success(self, mock_openai_client):
        """Test successful comic avatar creation and trait extraction."""
        from main import create_comic_avatar_and_extract_traits
        
        # Mock OpenAI responses
        mock_openai_client.chat.completions.create.side_effect = [
            Mock(choices=[Mock(message=Mock(content="Detailed character description from photo"))]),  # Description
            Mock(choices=[Mock(message=Mock(content="Visual traits: Brown mouse with big ears"))])  # Traits
        ]
        
        mock_openai_client.images.generate.return_value = Mock(
            data=[Mock(b64_json="base64comicavatar")]
        )
        
        avatar_bytes, visual_traits = await create_comic_avatar_and_extract_traits(
            uploaded_image_bytes=b"fake-photo-data",
            avatar_name="Benny",
            traits_description="Brave mouse",
            request_id="test-request-id"
        )
        
        assert avatar_bytes == base64.b64decode("base64comicavatar")
        assert "Brown mouse with big ears" in visual_traits
        assert mock_openai_client.chat.completions.create.call_count == 2
        assert mock_openai_client.images.generate.call_count == 1
    
    @pytest.mark.asyncio
    async def test_create_comic_avatar_no_image_data(self):
        """Test avatar creation with no image data."""
        from main import create_comic_avatar_and_extract_traits
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            await create_comic_avatar_and_extract_traits(
                uploaded_image_bytes=None,
                avatar_name="Test",
                traits_description="Test traits",
                request_id="test-id"
            )
        
        assert exc_info.value.status_code == 400
        assert "No image data provided" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_generate_avatar_background_task_success(self, mock_openai_client, mock_s3_client, mock_db_manager):
        """Test successful avatar generation in background task."""
        from main import generate_avatar_background_task
        
        # Mock avatar generation
        mock_openai_client.chat.completions.create.side_effect = [
            Mock(choices=[Mock(message=Mock(content="Character description"))]),
            Mock(choices=[Mock(message=Mock(content="Visual traits description"))])
        ]
        mock_openai_client.images.generate.return_value = Mock(
            data=[Mock(b64_json="avatarbase64")]
        )
        
        # Mock S3 upload
        with patch('main.save_avatar_to_s3', AsyncMock(return_value="https://s3/avatar.png")):
            with patch('core.database.update_avatar_status_with_traits', AsyncMock(return_value=True)):
                await generate_avatar_background_task(
                    avatar_id=1,
                    image_bytes=b"fake-image",
                    avatar_name="TestAvatar",
                    traits_description="Test traits",
                    request_id="test-id",
                    user_id=1
                )
        
        # Verify avatar was processed
        assert mock_openai_client.chat.completions.create.call_count == 2
        assert mock_openai_client.images.generate.call_count == 1
    
    @pytest.mark.asyncio
    async def test_generate_avatar_background_task_error(self, mock_openai_client):
        """Test error handling in avatar background task."""
        from main import generate_avatar_background_task
        
        # Mock error during generation
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")
        
        with patch('core.database.update_avatar_status', AsyncMock()) as mock_update_status:
            await generate_avatar_background_task(
                avatar_id=1,
                image_bytes=b"fake-image",
                avatar_name="TestAvatar",
                traits_description="Test traits",
                request_id="test-id",
                user_id=1
            )
        
        # Verify status was updated to FAILED
        mock_update_status.assert_called_with(1, "FAILED")
    
    @pytest.mark.asyncio
    async def test_create_avatar_multipart_upload(self, test_client, mock_db_manager, mock_openai_client):
        """Test avatar creation with multipart form upload."""
        # Mock user authentication
        mock_db_manager.execute_query.side_effect = [
            [{"id": 1}],  # User exists
            [{"id": 1, "email": "test@example.com"}],  # User lookup
            [{  # Avatar data
                "id": 1,
                "avatar_name": "Benny",
                "traits_description": "Brave mouse",
                "s3_image_url": "https://s3/avatar.png",
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
        
        # Mock OpenAI responses
        mock_openai_client.chat.completions.create.side_effect = [
            Mock(choices=[Mock(message=Mock(content="Character description"))]),
            Mock(choices=[Mock(message=Mock(content="Visual traits"))])
        ]
        mock_openai_client.images.generate.return_value = Mock(
            data=[Mock(b64_json="avatardata")]
        )
        
        with patch('main.JWTUtils') as mock_jwt:
            mock_jwt.verify_token.return_value = {"user_id": 1}
            
            with patch('main.save_avatar_to_s3', AsyncMock(return_value="https://s3/avatar.png")):
                # Create image file
                image_data = BytesIO(b"fake-image-data")
                files = {"image": ("avatar.jpg", image_data, "image/jpeg")}
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
        assert data["avatar_name"] == "Benny"
        assert "s3_image_url" in data
    
    @pytest.mark.asyncio
    async def test_comic_style_prompt_generation(self, mock_openai_client):
        """Test comic style prompt includes correct requirements."""
        from main import create_comic_avatar_and_extract_traits
        
        # Capture the prompts sent to OpenAI
        call_args_list = []
        
        async def capture_calls(*args, **kwargs):
            call_args_list.append(kwargs)
            if len(call_args_list) == 1:
                return Mock(choices=[Mock(message=Mock(content="Character description"))])
            else:
                return Mock(choices=[Mock(message=Mock(content="Visual traits"))])
        
        mock_openai_client.chat.completions.create = capture_calls
        mock_openai_client.images.generate.return_value = Mock(data=[Mock(b64_json="avatar")])
        
        await create_comic_avatar_and_extract_traits(
            uploaded_image_bytes=b"image",
            avatar_name="TestChar",
            traits_description="Test personality",
            request_id="test"
        )
        
        # Check character analysis prompt
        assert len(call_args_list) >= 1
        first_prompt = call_args_list[0]['messages'][1]['content'][0]['text']
        assert "TestChar" in first_prompt
        assert "Test personality" in first_prompt
        assert "comic book character" in first_prompt
        
        # Check image generation was called with style requirements
        image_call = mock_openai_client.images.generate.call_args[1]
        assert "comic book/cartoon style" in image_call['prompt']
        assert "Pixar/Disney" in image_call['prompt']
        assert "children aged 3-5" in image_call['prompt']