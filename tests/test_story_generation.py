"""
Unit tests for story generation functionality.
"""
import pytest
from unittest.mock import patch, Mock, AsyncMock, MagicMock
import base64
import json
from datetime import datetime


class TestStoryGeneration:
    """Test story generation functions."""
    
    @pytest.mark.asyncio
    async def test_generate_story_background_task_success(self, mock_openai_client, mock_db_manager):
        """Test successful story generation in background task."""
        from main import generate_story_background_task
        
        # Mock database operations
        mock_db_manager.execute_update = AsyncMock(return_value=1)
        mock_db_manager.execute_query = AsyncMock(return_value=[])
        
        # Mock story content
        story_content = "Title: The Brave Mouse\n\nOnce upon a time...\n\nThe End! (Created By - MyStoryBuddy)"
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = story_content
        
        # Mock image generation
        mock_openai_client.images.generate.return_value.data = [
            Mock(b64_json="base64image1"),
            Mock(b64_json="base64image2"),
            Mock(b64_json="base64image3"),
            Mock(b64_json="base64image4")
        ]
        
        # Run background task
        with patch('main.save_image_to_s3', AsyncMock(return_value="https://test.s3.amazonaws.com/image.png")):
            with patch('core.database.update_story_content', AsyncMock(return_value=True)):
                await generate_story_background_task(
                    story_id=1,
                    prompt="A brave mouse story",
                    formats=["Comic Book", "Text Story"],
                    request_id="test-request-id",
                    user_id="1"
                )
        
        # Verify OpenAI was called
        assert mock_openai_client.chat.completions.create.called
        assert mock_openai_client.images.generate.called
    
    @pytest.mark.asyncio
    async def test_generate_story_with_avatar_detection(self, mock_openai_client, mock_db_manager):
        """Test story generation with avatar detection and enrichment."""
        from main import generate_story_background_task
        
        # Mock avatar data
        avatar_data = {
            'id': 1,
            'avatar_name': 'Benny',
            'traits_description': 'A brave mouse',
            'visual_traits': 'Small brown mouse with big ears'
        }
        
        # Mock database calls for avatar detection
        mock_db_manager.execute_query = AsyncMock(side_effect=[
            [avatar_data],  # get_user_avatar
            []  # Other queries
        ])
        
        # Run background task with avatar name in prompt
        with patch('main.save_image_to_s3', AsyncMock(return_value="https://test.s3.amazonaws.com/image.png")):
            with patch('core.database.update_story_content', AsyncMock(return_value=True)):
                await generate_story_background_task(
                    story_id=1,
                    prompt="A story about Benny the mouse",
                    formats=["Comic Book"],
                    request_id="test-request-id",
                    user_id="1"
                )
        
        # Verify enriched prompt was used
        call_args = mock_openai_client.chat.completions.create.call_args
        user_message = call_args[1]['messages'][1]['content']
        assert "CHARACTER DETAILS FOR Benny" in user_message
        assert "brave mouse" in user_message
    
    @pytest.mark.asyncio
    async def test_generate_story_dev_mode(self, mock_openai_client, mock_db_manager):
        """Test story generation in dev mode returns static images."""
        from main import generate_story_background_task
        
        # Mock story content
        story_content = "Title: Dev Story\n\nTest story content.\n\nThe End! (Created By - MyStoryBuddy)"
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = story_content
        
        # Run with (dev) in prompt
        with patch('core.database.update_story_content', AsyncMock(return_value=True)) as mock_update:
            await generate_story_background_task(
                story_id=1,
                prompt="Test story (dev)",
                formats=["Comic Book"],
                request_id="test-request-id",
                user_id=None
            )
        
        # Verify static dev images were used
        mock_update.assert_called_once()
        call_args = mock_update.call_args[0]
        image_urls = call_args[3]  # Fourth argument is image_urls
        assert len(image_urls) == 4
        assert all("f5ef3161-7410-4770-a7d3-6cdadeb21437" in url for url in image_urls)
    
    @pytest.mark.asyncio
    async def test_generate_story_images_breakdown(self, mock_openai_client):
        """Test story breakdown into 4 comic parts."""
        from main import generate_story_images
        
        # Mock story breakdown response
        breakdown_content = """Part 1: Introduction
---PART BREAK---
Part 2: Development
---PART BREAK---
Part 3: Climax
---PART BREAK---
Part 4: Resolution"""
        
        mock_openai_client.chat.completions.create.side_effect = [
            Mock(choices=[Mock(message=Mock(content=breakdown_content))]),  # Breakdown
            Mock(choices=[Mock(message=Mock(content="Character description"))]),  # Consistency
            *[Mock(choices=[Mock(message=Mock(content=f"Image {i} prompt"))]) for i in range(4)]  # Image prompts
        ]
        
        # Mock image generation
        mock_openai_client.images.generate.return_value.data = [Mock(b64_json="base64imagedata")]
        
        with patch('main.save_image_to_s3', AsyncMock(return_value="https://test.s3.amazonaws.com/image.png")):
            result = await generate_story_images(
                story="Full story content",
                title="Test Story",
                request_id="test-id",
                original_prompt="Test prompt"
            )
        
        assert len(result) == 4
        assert all(url.startswith("https://") for url in result)
    
    @pytest.mark.asyncio
    async def test_generate_story_images_fallback_breakdown(self, mock_openai_client):
        """Test fallback story breakdown when AI doesn't return 4 parts."""
        from main import generate_story_images
        
        # Mock invalid breakdown response
        mock_openai_client.chat.completions.create.side_effect = [
            Mock(choices=[Mock(message=Mock(content="Invalid breakdown with only 2 parts"))]),  # Bad breakdown
            Mock(choices=[Mock(message=Mock(content="Character description"))]),  # Consistency
            *[Mock(choices=[Mock(message=Mock(content=f"Image {i} prompt"))]) for i in range(4)]  # Image prompts
        ]
        
        # Mock image generation
        mock_openai_client.images.generate.return_value.data = [Mock(b64_json="base64imagedata")]
        
        story_with_paragraphs = "Paragraph 1\n\nParagraph 2\n\nParagraph 3\n\nParagraph 4\n\nParagraph 5"
        
        with patch('main.save_image_to_s3', AsyncMock(return_value="https://test.s3.amazonaws.com/image.png")):
            result = await generate_story_images(
                story=story_with_paragraphs,
                title="Test Story",
                request_id="test-id",
                original_prompt="Test prompt"
            )
        
        assert len(result) == 4
    
    @pytest.mark.asyncio
    async def test_generate_story_error_handling(self, mock_openai_client, mock_db_manager):
        """Test error handling in story generation."""
        from main import generate_story_background_task
        
        # Mock OpenAI error
        mock_openai_client.chat.completions.create.side_effect = Exception("OpenAI API Error")
        
        # Mock update_story_content for error case
        with patch('core.database.update_story_content', AsyncMock(return_value=True)) as mock_update:
            await generate_story_background_task(
                story_id=1,
                prompt="Test story",
                formats=["Comic Book"],
                request_id="test-request-id",
                user_id=None
            )
        
        # Verify error story was saved
        mock_update.assert_called_with(
            1,
            "Story Generation Failed",
            "We encountered an error while generating your story. Please try again.",
            [],
            status='NEW'
        )
    
    @pytest.mark.asyncio
    async def test_detect_avatar_names_in_prompt(self):
        """Test avatar name detection in prompts."""
        from main import detect_avatar_names_in_prompt
        
        # Mock database query
        avatar_data = {
            'avatar_name': 'Benny',
            'traits_description': 'Brave mouse',
            'visual_traits': 'Brown mouse with big ears'
        }
        
        with patch('core.database.get_user_avatar', AsyncMock(return_value=avatar_data)):
            # Test with avatar name in prompt
            result = await detect_avatar_names_in_prompt("Tell me a story about Benny", 1)
            assert 'Benny' in result
            assert result['Benny'] == avatar_data
            
            # Test without avatar name
            result = await detect_avatar_names_in_prompt("Tell me a random story", 1)
            assert result == {}
            
            # Test case insensitive
            result = await detect_avatar_names_in_prompt("Tell me a story about BENNY", 1)
            assert 'Benny' in result
    
    @pytest.mark.asyncio
    async def test_enrich_prompt_with_avatar_traits(self):
        """Test prompt enrichment with avatar traits."""
        from main import enrich_prompt_with_avatar_traits
        
        detected_avatars = {
            'Benny': {
                'avatar_name': 'Benny',
                'traits_description': 'A brave and curious mouse',
                'visual_traits': 'Small brown mouse with big ears, wearing a blue vest'
            }
        }
        
        original_prompt = "Tell me a story about Benny"
        enriched = await enrich_prompt_with_avatar_traits(original_prompt, detected_avatars)
        
        assert "CHARACTER DETAILS FOR Benny:" in enriched
        assert "Personality: A brave and curious mouse" in enriched
        assert "Appearance: Small brown mouse with big ears, wearing a blue vest" in enriched
        assert original_prompt in enriched
    
    @pytest.mark.asyncio
    async def test_parallel_image_generation(self, mock_openai_client):
        """Test parallel generation of 4 comic images."""
        from main import generate_story_images
        
        # Mock responses
        mock_openai_client.chat.completions.create.side_effect = [
            Mock(choices=[Mock(message=Mock(content="Part 1\n---PART BREAK---\nPart 2\n---PART BREAK---\nPart 3\n---PART BREAK---\nPart 4"))]),
            Mock(choices=[Mock(message=Mock(content="Character consistency guide"))])
        ]
        
        # Track image generation calls
        generation_calls = []
        
        async def mock_generate(*args, **kwargs):
            generation_calls.append(kwargs)
            return Mock(data=[Mock(b64_json=f"image{len(generation_calls)}")])
        
        mock_openai_client.images.generate = mock_generate
        
        with patch('main.save_image_to_s3', AsyncMock(side_effect=lambda img, **kwargs: f"https://s3/image{kwargs.get('image_index', 0)}.png")):
            result = await generate_story_images(
                story="Test story",
                title="Test",
                request_id="test-id",
                original_prompt=""
            )
        
        # Verify 4 images were generated
        assert len(generation_calls) == 4
        assert len(result) == 4
        
        # Verify each image has unique index in URL
        for i, url in enumerate(result):
            assert f"image{i+1}.png" in url