"""
Sample data and fixtures for testing.
"""
from datetime import datetime
import json


class SampleData:
    """Sample data for testing purposes."""
    
    SAMPLE_USERS = [
        {
            'id': 1,
            'email': 'john.doe@example.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'password_hash': '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiGpO6EsjO7y',  # 'password123'
            'auth_type': 'email_password',
            'is_active': True,
            'created_at': datetime(2024, 1, 1, 12, 0, 0),
            'updated_at': datetime(2024, 1, 1, 12, 0, 0)
        },
        {
            'id': 2,
            'email': 'jane.smith@example.com',
            'first_name': 'Jane',
            'last_name': 'Smith',
            'password_hash': None,  # OTP-only user
            'auth_type': 'otp',
            'is_active': True,
            'created_at': datetime(2024, 1, 2, 12, 0, 0),
            'updated_at': datetime(2024, 1, 2, 12, 0, 0)
        },
        {
            'id': 3,
            'email': 'bob.wilson@gmail.com',
            'first_name': 'Bob',
            'last_name': 'Wilson',
            'password_hash': None,
            'auth_type': 'google',
            'is_active': True,
            'created_at': datetime(2024, 1, 3, 12, 0, 0),
            'updated_at': datetime(2024, 1, 3, 12, 0, 0)
        }
    ]
    
    SAMPLE_STORIES = [
        {
            'id': 1,
            'title': 'The Brave Little Mouse',
            'story_content': 'Once upon a time, there was a brave little mouse named Benny. He lived in a cozy hole under the old oak tree. One day, Benny decided to explore the big garden.\n\nBenny discovered a beautiful flower garden with colorful butterflies dancing around. He made friends with a friendly ladybug named Lucy who showed him around.\n\nSudenly, dark clouds gathered and it started to rain. Benny and Lucy found shelter under a big mushroom. They waited together until the sun came out again.\n\nWhen the rain stopped, a beautiful rainbow appeared in the sky. Benny realized that adventures are even better when shared with friends.\n\nThe End! (Created By - MyStoryBuddy)',
            'prompt': 'Tell me a story about a brave little mouse',
            'image_urls': json.dumps([
                'https://mystorybuddy-assets.s3.amazonaws.com/stories/test1_image_1.png',
                'https://mystorybuddy-assets.s3.amazonaws.com/stories/test1_image_2.png',
                'https://mystorybuddy-assets.s3.amazonaws.com/stories/test1_image_3.png',
                'https://mystorybuddy-assets.s3.amazonaws.com/stories/test1_image_4.png'
            ]),
            'formats': json.dumps(['Comic Book', 'Text Story']),
            'created_at': datetime(2024, 1, 1, 14, 0, 0),
            'updated_at': datetime(2024, 1, 1, 14, 30, 0),
            'user_id': '1',
            'request_id': 'test-request-1',
            'status': 'NEW'
        },
        {
            'id': 2,
            'title': 'The Magic Forest Adventure',
            'story_content': 'In a magical forest far away, lived a curious rabbit named Ruby. She had soft white fur and bright pink eyes that sparkled with wonder.\n\nOne morning, Ruby discovered a hidden path covered with glowing flowers. She followed the path deeper into the forest, where she met a wise old owl named Oliver.\n\nOliver told Ruby about a secret waterfall that granted one wish to kind-hearted creatures. Ruby wanted to wish for happiness for all forest animals.\n\nTogether, they found the magical waterfall. Ruby made her wish, and suddenly, all the forest animals appeared, laughing and playing together in harmony.\n\nThe End! (Created By - MyStoryBuddy)',
            'prompt': 'A magical forest story',
            'image_urls': json.dumps([
                'https://mystorybuddy-assets.s3.amazonaws.com/stories/test2_image_1.png',
                'https://mystorybuddy-assets.s3.amazonaws.com/stories/test2_image_2.png',
                'https://mystorybuddy-assets.s3.amazonaws.com/stories/test2_image_3.png',
                'https://mystorybuddy-assets.s3.amazonaws.com/stories/test2_image_4.png'
            ]),
            'formats': json.dumps(['Comic Book']),
            'created_at': datetime(2024, 1, 2, 10, 0, 0),
            'updated_at': datetime(2024, 1, 2, 10, 25, 0),
            'user_id': '2',
            'request_id': 'test-request-2',
            'status': 'VIEWED'
        },
        {
            'id': 3,
            'title': 'Story in Progress...',
            'story_content': 'Your story is being generated...',
            'prompt': 'A story about dinosaurs',
            'image_urls': json.dumps([]),
            'formats': json.dumps(['Comic Book']),
            'created_at': datetime(2024, 1, 3, 16, 0, 0),
            'updated_at': datetime(2024, 1, 3, 16, 0, 0),
            'user_id': '1',
            'request_id': 'test-request-3',
            'status': 'IN_PROGRESS'
        }
    ]
    
    SAMPLE_AVATARS = [
        {
            'id': 1,
            'user_id': 1,
            'avatar_name': 'Benny',
            'traits_description': 'A brave and curious mouse who loves exploring new places and making friends. He is kind, helpful, and always ready for adventure.',
            's3_image_url': 'https://mystorybuddy-assets.s3.amazonaws.com/avatars/user_1_benny.png',
            'visual_traits': 'Small brown mouse with big round ears, bright black eyes, wearing a tiny blue vest with golden buttons. Has a friendly smile and an adventurous spirit.',
            'status': 'COMPLETED',
            'is_active': True,
            'created_at': datetime(2024, 1, 1, 15, 0, 0),
            'updated_at': datetime(2024, 1, 1, 15, 30, 0)
        },
        {
            'id': 2,
            'user_id': 2,
            'avatar_name': 'Ruby',
            'traits_description': 'A gentle and wise rabbit who loves nature and helping others. She is patient, caring, and has a deep connection with the forest.',
            's3_image_url': 'https://mystorybuddy-assets.s3.amazonaws.com/avatars/user_2_ruby.png',
            'visual_traits': 'Soft white rabbit with pink eyes and long floppy ears. Wears a flower crown made of daisies and has a peaceful, serene expression.',
            'status': 'COMPLETED',
            'is_active': True,
            'created_at': datetime(2024, 1, 2, 11, 0, 0),
            'updated_at': datetime(2024, 1, 2, 11, 20, 0)
        },
        {
            'id': 3,
            'user_id': 3,
            'avatar_name': 'Max',
            'traits_description': 'A playful and energetic puppy who loves to run, jump, and play fetch. He is loyal, friendly, and always excited to meet new friends.',
            's3_image_url': '',
            'visual_traits': None,
            'status': 'IN_PROGRESS',
            'is_active': True,
            'created_at': datetime(2024, 1, 3, 14, 0, 0),
            'updated_at': datetime(2024, 1, 3, 14, 0, 0)
        }
    ]
    
    SAMPLE_FUN_FACTS = [
        {
            'id': 1,
            'prompt': 'Tell me about animals',
            'facts': json.dumps([
                {
                    'question': 'Did you know that elephants can recognize themselves in mirrors?',
                    'answer': 'Yes! Elephants are one of the few animals that can pass the mirror test, showing they understand the reflection is themselves.'
                },
                {
                    'question': 'Did you know that octopuses have three hearts?',
                    'answer': 'Amazing! Two hearts pump blood to the gills, and one pumps blood to the rest of the body.'
                },
                {
                    'question': 'Did you know that honeybees communicate through dancing?',
                    'answer': 'They do! Bees perform a "waggle dance" to tell other bees where to find the best flowers.'
                }
            ]),
            'created_at': datetime(2024, 1, 1, 16, 0, 0),
            'request_id': 'test-facts-1'
        },
        {
            'id': 2,
            'prompt': 'Space facts for kids',
            'facts': json.dumps([
                {
                    'question': 'Did you know that the Sun is a star?',
                    'answer': 'Yes! The Sun is actually a giant star that gives us light and warmth every day.'
                },
                {
                    'question': 'Did you know that there are billions of stars in the sky?',
                    'answer': 'There are so many stars that we could never count them all, even if we tried our whole lives!'
                }
            ]),
            'created_at': datetime(2024, 1, 2, 17, 0, 0),
            'request_id': 'test-facts-2'
        }
    ]
    
    SAMPLE_AUTH_SESSIONS = [
        {
            'id': 1,
            'user_id': 1,
            'access_token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.sample.token',
            'expires_at': datetime(2024, 12, 31, 23, 59, 59),
            'created_at': datetime(2024, 1, 1, 12, 0, 0),
            'is_active': True
        },
        {
            'id': 2,
            'user_id': 2,
            'access_token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.another.token',
            'expires_at': datetime(2024, 12, 31, 23, 59, 59),
            'created_at': datetime(2024, 1, 2, 12, 0, 0),
            'is_active': True
        }
    ]
    
    SAMPLE_OTP_CODES = [
        {
            'id': 1,
            'email': 'test@example.com',
            'otp': '123456',
            'created_at': datetime(2024, 1, 1, 12, 0, 0),
            'expires_at': datetime(2024, 1, 1, 12, 5, 0),
            'used': False
        },
        {
            'id': 2,
            'email': 'jane.smith@example.com',
            'otp': '654321',
            'created_at': datetime(2024, 1, 2, 10, 0, 0),
            'expires_at': datetime(2024, 1, 2, 10, 5, 0),
            'used': True
        }
    ]
    
    OPENAI_RESPONSES = {
        'story_generation': {
            'simple_story': 'Title: The Happy Butterfly\n\nOnce upon a time, there was a colorful butterfly named Bella. She loved flying through the sunny garden and visiting all the beautiful flowers.\n\nBella met a friendly bee named Buzz who was collecting nectar. They became best friends and decided to explore the garden together.\n\nThey discovered a hidden pond with lily pads and friendly frogs. The frogs sang beautiful songs that made Bella and Buzz very happy.\n\nAt the end of the day, Bella and Buzz promised to meet again tomorrow for more adventures in the wonderful garden.\n\nThe End! (Created By - MyStoryBuddy)',
            
            'character_story': 'Title: Benny\'s Big Adventure\n\nBenny the brave mouse woke up feeling excited about exploring the big barn behind his home. He packed his tiny backpack with cheese crumbs and set off on his adventure.\n\nInside the barn, Benny met a wise old cat named Whiskers who surprisingly became his friend. Whiskers showed Benny all the secret hiding spots in the barn.\n\nTogether, they discovered a family of field mice who were lost and couldn\'t find their way home. Benny and Whiskers decided to help them.\n\nUsing Benny\'s bravery and Whiskers\' knowledge, they safely guided the lost mice back to their home in the meadow. Everyone was very grateful.\n\nThe End! (Created By - MyStoryBuddy)'
        },
        
        'fun_facts': [
            'Q: Did you know that cats can make over 100 different sounds?\nA: Yes! Dogs can only make about 10 sounds, but cats are much more talkative!\n\nQ: Did you know that a group of flamingos is called a "flamboyance"?\nA: What a perfect name for these bright pink, fancy birds!\n\nQ: Did you know that butterflies taste with their feet?\nA: When they land on flowers, they can taste if the nectar is yummy!',
            
            'Q: Did you know that reading stories helps your brain grow?\nA: Every time you read, your imagination gets stronger and stronger!\n\nQ: Did you know that laughing is good exercise?\nA: When you laugh really hard, it\'s like giving your belly muscles a workout!\n\nQ: Did you know that dreaming helps you learn?\nA: While you sleep, your brain practices all the things you learned during the day!'
        ],
        
        'character_descriptions': [
            'This image shows a cheerful character with distinctive features: round face with rosy cheeks, bright expressive eyes, and a warm smile. The character appears to be wearing casual, colorful clothing that suggests a playful and friendly personality.',
            
            'The character in this image has the appearance of a brave explorer: wearing adventure gear, has determined eyes, and carries themselves with confidence. Their expression suggests curiosity and readiness for discovery.'
        ],
        
        'visual_traits': [
            'Character design features: Small stature with proportionate build, wearing bright blue overalls with yellow buttons, brown hair in a messy but endearing style, green eyes that sparkle with mischief, freckles across the nose, and sneakers that look ready for adventure.',
            
            'Visual characteristics: Medium height with an athletic build, wearing explorer\'s vest with multiple pockets, sandy blonde hair tied back practically, bright blue eyes that show determination, sun-kissed skin suggesting outdoor adventures, and sturdy boots perfect for hiking.'
        ]
    }
    
    SAMPLE_REQUESTS = {
        'story_requests': [
            {
                'prompt': 'Tell me a story about a brave little mouse',
                'formats': ['Comic Book', 'Text Story']
            },
            {
                'prompt': 'A magical adventure in the forest',
                'formats': ['Comic Book']
            },
            {
                'prompt': '',  # Empty prompt for default story
                'formats': ['Text Story']
            }
        ],
        
        'fun_fact_requests': [
            {
                'prompt': 'Tell me fun facts about animals'
            },
            {
                'prompt': 'Space facts for kids'
            },
            {
                'prompt': ''  # Empty prompt for general facts
            }
        ],
        
        'auth_requests': [
            {
                'signup': {
                    'email': 'newuser@example.com',
                    'password': 'SecurePass123!',
                    'first_name': 'New',
                    'last_name': 'User'
                }
            },
            {
                'login': {
                    'email': 'john.doe@example.com',
                    'password': 'password123'
                }
            },
            {
                'otp_request': {
                    'email': 'test@example.com'
                }
            },
            {
                'otp_verify': {
                    'email': 'test@example.com',
                    'otp': '123456'
                }
            }
        ]
    }


class MockResponses:
    """Mock responses for external API calls."""
    
    @staticmethod
    def openai_chat_completion(content: str):
        """Mock OpenAI chat completion response."""
        from unittest.mock import Mock
        
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content=content))
        ]
        return mock_response
    
    @staticmethod
    def openai_image_generation(image_data: str = "base64encodedimage"):
        """Mock OpenAI image generation response."""
        from unittest.mock import Mock
        
        mock_response = Mock()
        mock_response.data = [Mock(b64_json=image_data)]
        return mock_response
    
    @staticmethod
    def s3_upload_success(etag: str = "test-etag"):
        """Mock successful S3 upload response."""
        return {'ETag': f'"{etag}"'}
    
    @staticmethod
    def database_query_result(data: list):
        """Mock database query result."""
        return data
    
    @staticmethod
    def database_update_result(affected_rows: int = 1):
        """Mock database update result."""
        return affected_rows


class TestDataBuilder:
    """Builder class for creating test data."""
    
    @staticmethod
    def create_user(user_id: int = 1, email: str = None, first_name: str = None):
        """Create a test user with optional overrides."""
        base_user = SampleData.SAMPLE_USERS[0].copy()
        
        if user_id:
            base_user['id'] = user_id
        if email:
            base_user['email'] = email
        if first_name:
            base_user['first_name'] = first_name
            
        return base_user
    
    @staticmethod
    def create_story(story_id: int = 1, user_id: str = None, status: str = None):
        """Create a test story with optional overrides."""
        base_story = SampleData.SAMPLE_STORIES[0].copy()
        
        if story_id:
            base_story['id'] = story_id
        if user_id:
            base_story['user_id'] = user_id
        if status:
            base_story['status'] = status
            
        return base_story
    
    @staticmethod
    def create_avatar(avatar_id: int = 1, user_id: int = None, status: str = None):
        """Create a test avatar with optional overrides."""
        base_avatar = SampleData.SAMPLE_AVATARS[0].copy()
        
        if avatar_id:
            base_avatar['id'] = avatar_id
        if user_id:
            base_avatar['user_id'] = user_id
        if status:
            base_avatar['status'] = status
            
        return base_avatar
    
    @staticmethod
    def create_auth_token(user_id: int = 1, expires_hours: int = 24):
        """Create a test JWT token."""
        from datetime import datetime, timedelta
        
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(hours=expires_hours)
        }
        
        # Return mock token since we don't need real JWT for tests
        return f"test-jwt-token-user-{user_id}"