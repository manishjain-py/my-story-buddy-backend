"""
Pytest configuration and shared fixtures for My Story Buddy backend tests.
"""
import os
import sys
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
import json
from contextlib import ExitStack

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Configure test environment variables
os.environ['TESTING'] = 'true'
os.environ['OPENAI_API_KEY'] = 'test-api-key'
os.environ['AWS_ACCESS_KEY_ID'] = 'test-access-key'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'test-secret-key'
os.environ['AWS_REGION'] = 'us-east-1'
os.environ['DB_PASSWORD'] = 'test-password'
os.environ['JWT_SECRET_KEY'] = 'test-jwt-secret-key-for-testing'
os.environ['GOOGLE_CLIENT_ID'] = 'test-google-client-id'
os.environ['GOOGLE_CLIENT_SECRET'] = 'test-google-client-secret'
os.environ['GOOGLE_REDIRECT_URI'] = 'http://localhost:8003/auth/google/callback'
os.environ['FRONTEND_URL'] = 'http://localhost:3000'


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    mock_client = AsyncMock()
    
    # Mock chat completions
    mock_response = Mock()
    mock_response.choices = [
        Mock(message=Mock(content="Title: Test Story\n\nThis is a test story.\n\nThe End! (Created By - MyStoryBuddy)"))
    ]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    # Mock image generation
    mock_image_response = Mock()
    mock_image_response.data = [Mock(b64_json="base64encodedimagedata")]
    mock_client.images.generate = AsyncMock(return_value=mock_image_response)
    
    return mock_client


@pytest.fixture
def mock_s3_client():
    """Mock S3 client for testing."""
    mock_client = Mock()
    mock_client.put_object = Mock(return_value={'ETag': '"test-etag"'})
    mock_client.list_objects_v2 = Mock(return_value={'Contents': []})
    mock_client.generate_presigned_url = Mock(return_value="https://test-bucket.s3.amazonaws.com/test-key")
    return mock_client


@pytest_asyncio.fixture
async def mock_db_manager():
    """Mock database manager for testing."""
    mock_manager = AsyncMock()
    mock_manager.pool = Mock()  # Truthy value for initialized check
    mock_manager.initialize = AsyncMock()
    mock_manager.close = AsyncMock()
    mock_manager.test_connection = AsyncMock()
    mock_manager.execute_query = AsyncMock(return_value=[])
    mock_manager.execute_update = AsyncMock(return_value=1)
    
    # Mock connection context manager
    mock_conn = AsyncMock()
    mock_cursor = AsyncMock()
    mock_cursor.execute = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[])
    mock_cursor.fetchone = AsyncMock(return_value=None)
    mock_cursor.rowcount = 1
    mock_cursor.lastrowid = 1
    
    mock_conn.cursor = Mock()
    mock_conn.cursor.return_value.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)
    
    # Set up get_connection to return the mock connection
    mock_connection_cm = AsyncMock()
    mock_connection_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_connection_cm.__aexit__ = AsyncMock(return_value=None)
    mock_manager.get_connection = AsyncMock(return_value=mock_connection_cm)
    
    return mock_manager


@pytest.fixture
def sample_user():
    """Sample user data for testing."""
    return {
        'id': 1,
        'email': 'test@example.com',
        'first_name': 'Test',
        'last_name': 'User',
        'password_hash': '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiGpO6EsjO7y',  # 'password123'
        'auth_type': 'email_password',
        'is_active': True,
        'created_at': datetime.now(),
        'updated_at': datetime.now()
    }


@pytest.fixture
def sample_story_request():
    """Sample story request data."""
    return {
        "prompt": "A story about a brave little mouse",
        "formats": ["Comic Book", "Text Story"]
    }


@pytest.fixture
def sample_avatar_data():
    """Sample avatar data for testing."""
    return {
        'id': 1,
        'user_id': 1,
        'avatar_name': 'Benny',
        'traits_description': 'A brave and curious mouse who loves adventures',
        's3_image_url': 'https://mystorybuddy-assets.s3.amazonaws.com/avatars/user_1_test.png',
        'visual_traits': 'Small brown mouse with big ears, wearing a tiny blue vest',
        'status': 'COMPLETED',
        'is_active': True,
        'created_at': datetime.now(),
        'updated_at': datetime.now()
    }


@pytest.fixture
def auth_headers():
    """Generate test authentication headers."""
    return {
        "Authorization": "Bearer test-jwt-token"
    }


@pytest.fixture
def mock_jwt_utils():
    """Mock JWT utilities for testing."""
    with patch('auth.auth_utils.JWTUtils.create_access_token') as mock_create, \
         patch('auth.auth_utils.JWTUtils.verify_token') as mock_verify:
        mock_create.return_value = "test-jwt-token"
        mock_verify.return_value = {"user_id": 1, "exp": 9999999999}
        yield {"create": mock_create, "verify": mock_verify}


@pytest.fixture
def mock_email_service():
    """Mock email service for testing."""
    mock_service = AsyncMock()
    mock_service.send_welcome_email = AsyncMock(return_value=True)
    mock_service.send_otp_email = AsyncMock(return_value=True)
    return mock_service


@pytest.fixture
def test_client_base(mock_openai_client, mock_s3_client, mock_db_manager):
    """Create test client with mocked dependencies."""
    from fastapi.testclient import TestClient
    
    # Comprehensive database mocking at all import levels
    patches = [
        # Mock the main application dependencies
        patch('main.client', mock_openai_client),
        patch('main.s3_client', mock_s3_client),
        patch('main.db_manager', mock_db_manager),
        
        # Mock database manager at core level
        patch('core.database.db_manager', mock_db_manager),
        
        # Mock all UserDatabase methods that import db_manager internally
        patch('auth.auth_models.UserDatabase.create_user', new_callable=AsyncMock),
        patch('auth.auth_models.UserDatabase.get_user_by_email', new_callable=AsyncMock),
        patch('auth.auth_models.UserDatabase.get_user_by_id', new_callable=AsyncMock),
        patch('auth.auth_models.UserDatabase.store_otp', new_callable=AsyncMock),
        patch('auth.auth_models.UserDatabase.verify_otp', new_callable=AsyncMock),
        patch('auth.auth_models.UserDatabase.invalidate_auth_session', new_callable=AsyncMock),
        patch('auth.auth_models.UserDatabase.create_auth_session', new_callable=AsyncMock),
        patch('auth.auth_models.UserDatabase.verify_auth_session', new_callable=AsyncMock),
        patch('auth.auth_models.UserDatabase.update_last_login', new_callable=AsyncMock),
        
        # Mock database functions that import db_manager internally
        patch('core.database.save_story', new_callable=AsyncMock),
        patch('core.database.save_fun_facts', new_callable=AsyncMock),
        patch('core.database.get_recent_stories', new_callable=AsyncMock),
        patch('core.database.create_story_placeholder', new_callable=AsyncMock),
        patch('core.database.update_story_content', new_callable=AsyncMock),
        patch('core.database.update_story_status', new_callable=AsyncMock),
        patch('core.database.get_story_by_id', new_callable=AsyncMock),
        patch('core.database.get_new_stories_count', new_callable=AsyncMock),
        patch('core.database.create_user_avatar', new_callable=AsyncMock),
        patch('core.database.get_user_avatar', new_callable=AsyncMock),
        patch('core.database.update_user_avatar', new_callable=AsyncMock),
        patch('core.database.update_avatar_status_with_traits', new_callable=AsyncMock),
        patch('core.database.get_completed_avatars_count', new_callable=AsyncMock),
        patch('core.database.cleanup_invalid_stories', new_callable=AsyncMock),
        
        # Mock email service
        patch('core.email_service.email_service.send_welcome_email', new_callable=AsyncMock),
        patch('core.email_service.email_service.send_otp_email', new_callable=AsyncMock),
    ]
    
    with ExitStack() as stack:
        # Apply all patches
        mocked_functions = {}
        for patch_obj in patches:
            mock_obj = stack.enter_context(patch_obj)
            # Store reference to mock for configuration
            if hasattr(patch_obj, 'attribute'):
                attr_name = patch_obj.attribute.split('.')[-1]
                mocked_functions[attr_name] = mock_obj
        
        # Configure auth model mocks for successful operations
        mock_create_user = mocked_functions.get('create_user')
        mock_get_user_by_email = mocked_functions.get('get_user_by_email')
        mock_get_user_by_id = mocked_functions.get('get_user_by_id')
        mock_verify_otp = mocked_functions.get('verify_otp')
        mock_store_otp = mocked_functions.get('store_otp')
        mock_send_welcome_email = mocked_functions.get('send_welcome_email')
        mock_send_otp_email = mocked_functions.get('send_otp_email')
        
        if mock_create_user:
            mock_create_user.return_value = 1  # Return user ID
        
        # Store this for tests to customize behavior per test
        default_user = {
            "id": 1, 
            "email": "test@example.com", 
            "first_name": "Test", 
            "last_name": "User",
            "auth_type": "email_password",
            "is_active": True,
            "created_at": "2025-01-01T00:00:00",
            "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiGpO6EsjO7y"  # 'password123'
        }
        
        if mock_get_user_by_email:
            # Default to None for signup tests, but tests can override this
            mock_get_user_by_email.return_value = None
        if mock_get_user_by_id:
            mock_get_user_by_id.return_value = default_user
        if mock_verify_otp:
            mock_verify_otp.return_value = True
        if mock_store_otp:
            mock_store_otp.return_value = None
        if mock_send_welcome_email:
            mock_send_welcome_email.return_value = True
        if mock_send_otp_email:
            mock_send_otp_email.return_value = True
        
        # Configure story/database operation mocks
        mock_save_story = mocked_functions.get('save_story')
        mock_create_story_placeholder = mocked_functions.get('create_story_placeholder')
        mock_update_story_content = mocked_functions.get('update_story_content')
        mock_get_story_by_id = mocked_functions.get('get_story_by_id')
        mock_create_user_avatar = mocked_functions.get('create_user_avatar')
        mock_get_user_avatar = mocked_functions.get('get_user_avatar')
        
        if mock_save_story:
            mock_save_story.return_value = 1
        if mock_create_story_placeholder:
            mock_create_story_placeholder.return_value = 1
        if mock_update_story_content:
            mock_update_story_content.return_value = True
        if mock_get_story_by_id:
            mock_get_story_by_id.return_value = {
                "id": 1,
                "title": "Test Story",
                "story_content": "This is a test story",
                "status": "NEW",
                "image_urls": ["https://test.com/image.png"]
            }
        if mock_create_user_avatar:
            mock_create_user_avatar.return_value = 1
        if mock_get_user_avatar:
            mock_get_user_avatar.return_value = {
                "id": 1,
                "avatar_name": "Test Avatar",
                "traits_description": "A test avatar",
                "s3_image_url": "https://test.com/avatar.png",
                "status": "COMPLETED"
            }
        
        # Import app after all patching is complete
        from main import app
        
        # Create test client
        client = TestClient(app)
        yield client


@pytest.fixture
def test_client(test_client_base):
    """Default test client - compatible with most tests."""
    return test_client_base


@pytest.fixture  
def test_client_with_user(mock_openai_client, mock_s3_client, mock_db_manager, sample_user):
    """Test client with existing user mocked for login tests."""
    from fastapi.testclient import TestClient
    
    # Same patches as base but with user existing
    patches = [
        # Mock the main application dependencies
        patch('main.client', mock_openai_client),
        patch('main.s3_client', mock_s3_client),
        patch('main.db_manager', mock_db_manager),
        
        # Mock database manager at core level
        patch('core.database.db_manager', mock_db_manager),
        
        # Mock all UserDatabase methods that import db_manager internally
        patch('auth.auth_models.UserDatabase.create_user', new_callable=AsyncMock),
        patch('auth.auth_models.UserDatabase.get_user_by_email', new_callable=AsyncMock),
        patch('auth.auth_models.UserDatabase.get_user_by_id', new_callable=AsyncMock),
        patch('auth.auth_models.UserDatabase.store_otp', new_callable=AsyncMock),
        patch('auth.auth_models.UserDatabase.verify_otp', new_callable=AsyncMock),
        patch('auth.auth_models.UserDatabase.invalidate_auth_session', new_callable=AsyncMock),
        patch('auth.auth_models.UserDatabase.create_auth_session', new_callable=AsyncMock),
        patch('auth.auth_models.UserDatabase.verify_auth_session', new_callable=AsyncMock),
        patch('auth.auth_models.UserDatabase.update_last_login', new_callable=AsyncMock),
        
        # Mock database functions that import db_manager internally
        patch('core.database.save_story', new_callable=AsyncMock),
        patch('core.database.save_fun_facts', new_callable=AsyncMock),
        patch('core.database.get_recent_stories', new_callable=AsyncMock),
        patch('core.database.create_story_placeholder', new_callable=AsyncMock),
        patch('core.database.update_story_content', new_callable=AsyncMock),
        patch('core.database.update_story_status', new_callable=AsyncMock),
        patch('core.database.get_story_by_id', new_callable=AsyncMock),
        patch('core.database.get_new_stories_count', new_callable=AsyncMock),
        patch('core.database.create_user_avatar', new_callable=AsyncMock),
        patch('core.database.get_user_avatar', new_callable=AsyncMock),
        patch('core.database.update_user_avatar', new_callable=AsyncMock),
        patch('core.database.update_avatar_status_with_traits', new_callable=AsyncMock),
        patch('core.database.get_completed_avatars_count', new_callable=AsyncMock),
        patch('core.database.cleanup_invalid_stories', new_callable=AsyncMock),
        
        # Mock email service
        patch('core.email_service.email_service.send_welcome_email', new_callable=AsyncMock),
        patch('core.email_service.email_service.send_otp_email', new_callable=AsyncMock),
    ]
    
    with ExitStack() as stack:
        # Apply all patches
        mocked_functions = {}
        for patch_obj in patches:
            mock_obj = stack.enter_context(patch_obj)
            # Store reference to mock for configuration
            if hasattr(patch_obj, 'attribute'):
                attr_name = patch_obj.attribute.split('.')[-1]
                mocked_functions[attr_name] = mock_obj
        
        # Configure auth model mocks for existing user (login scenario)
        mock_create_user = mocked_functions.get('create_user')
        mock_get_user_by_email = mocked_functions.get('get_user_by_email')
        mock_get_user_by_id = mocked_functions.get('get_user_by_id')
        mock_verify_otp = mocked_functions.get('verify_otp')
        mock_store_otp = mocked_functions.get('store_otp')
        mock_send_welcome_email = mocked_functions.get('send_welcome_email')
        mock_send_otp_email = mocked_functions.get('send_otp_email')
        
        if mock_create_user:
            mock_create_user.return_value = 1  # Return user ID
        if mock_get_user_by_email:
            mock_get_user_by_email.return_value = sample_user  # Return existing user for login
        if mock_get_user_by_id:
            mock_get_user_by_id.return_value = sample_user
        if mock_verify_otp:
            mock_verify_otp.return_value = True
        if mock_store_otp:
            mock_store_otp.return_value = None
        if mock_send_welcome_email:
            mock_send_welcome_email.return_value = True
        if mock_send_otp_email:
            mock_send_otp_email.return_value = True
        
        # Import app after all patching is complete
        from main import app
        
        # Create test client
        client = TestClient(app)
        yield client


@pytest.fixture
def mock_request():
    """Mock FastAPI Request object."""
    request = Mock()
    request.headers = {"Authorization": "Bearer test-token"}
    request.client = Mock(host="127.0.0.1")
    request.method = "POST"
    request.url = Mock(path="/generateStory")
    return request