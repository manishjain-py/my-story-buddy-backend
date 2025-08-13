# My Story Buddy Backend - Test Suite

This directory contains comprehensive unit and integration tests for the My Story Buddy backend application.

## Overview

The test suite provides complete coverage of the backend functionality including:

- **Story Generation**: Testing AI-powered story creation with OpenAI integration
- **Image Generation**: Testing comic-style image generation and S3 storage
- **Authentication**: Testing user signup, login, OTP verification, and JWT handling
- **Avatar Management**: Testing avatar creation, processing, and storage
- **Database Operations**: Testing all CRUD operations and migrations
- **API Endpoints**: Testing all FastAPI routes and middleware
- **Error Handling**: Testing edge cases and failure scenarios
- **Integration Workflows**: Testing complete end-to-end user journeys

## Test Structure

```
tests/
├── conftest.py              # Pytest configuration and shared fixtures
├── fixtures/                # Test data and mock objects
│   ├── __init__.py
│   └── sample_data.py       # Sample users, stories, avatars, etc.
├── test_main.py            # Main FastAPI application tests
├── test_auth.py            # Authentication and authorization tests
├── test_story_generation.py # Story generation functionality tests
├── test_avatar_generation.py # Avatar creation and processing tests
├── test_database.py        # Database operations tests
├── test_utilities.py       # Utility functions and helper tests
├── test_integration.py     # End-to-end integration tests
├── requirements-test.txt   # Testing dependencies
└── README.md              # This file
```

## Test Categories

### Unit Tests
- **Test Coverage**: Individual functions and classes
- **Mock Dependencies**: External APIs (OpenAI, S3, Database)
- **Fast Execution**: Isolated tests without external dependencies
- **Markers**: Use `@pytest.mark.unit` or run with `-m "not integration"`

### Integration Tests
- **Test Coverage**: Complete workflows and user journeys
- **Real Interactions**: Tests how components work together
- **Comprehensive Scenarios**: Success paths and error handling
- **Markers**: Use `@pytest.mark.integration` or run with `-m integration`

## Running Tests

### Prerequisites
```bash
# Install test dependencies
pip install -r tests/requirements-test.txt

# Or use the Makefile
make install-dev
```

### Run All Tests
```bash
# From project root
make test

# Or directly with pytest
cd src && python -m pytest ../tests/ -v
```

### Run Specific Test Types
```bash
# Unit tests only
make test-unit

# Integration tests only
make test-integration

# Tests with coverage report
make test-coverage
```

### Run Specific Test Files
```bash
# Story generation tests
cd src && python -m pytest ../tests/test_story_generation.py -v

# Authentication tests
cd src && python -m pytest ../tests/test_auth.py -v

# Database tests
cd src && python -m pytest ../tests/test_database.py -v
```

### Run Tests with Markers
```bash
# Run only authentication-related tests
cd src && python -m pytest ../tests/ -m auth

# Run only story-related tests
cd src && python -m pytest ../tests/ -m story

# Exclude slow tests
cd src && python -m pytest ../tests/ -m "not slow"
```

## Test Configuration

### Environment Variables
Tests automatically configure the following environment variables:
- `TESTING=true`
- `OPENAI_API_KEY=test-api-key`
- `AWS_ACCESS_KEY_ID=test-access-key`
- `AWS_SECRET_ACCESS_KEY=test-secret-key`
- `JWT_SECRET_KEY=test-jwt-secret-key`

### Mocking Strategy
- **OpenAI Client**: Mocked to return predictable responses
- **S3 Client**: Mocked to simulate upload success/failure
- **Database**: Mocked with controlled return values
- **Email Service**: Mocked to prevent actual email sending

## Key Test Fixtures

### `test_client`
FastAPI test client with all dependencies mocked:
```python
def test_example(test_client):
    response = test_client.get("/health")
    assert response.status_code == 200
```

### `sample_user`
Pre-configured user data for authentication tests:
```python
def test_user_operations(sample_user):
    assert sample_user["email"] == "test@example.com"
    assert sample_user["first_name"] == "Test"
```

### `mock_openai_client`
Configured OpenAI client mock:
```python
@pytest.mark.asyncio
async def test_story_generation(mock_openai_client):
    # Client is pre-configured with story and image responses
    result = await generate_story("test prompt")
    assert "Title:" in result
```

### `mock_db_manager`
Database manager with configurable responses:
```python
@pytest.mark.asyncio
async def test_database_operations(mock_db_manager):
    mock_db_manager.execute_query.return_value = [{"id": 1}]
    result = await get_story_by_id(1)
    assert result["id"] == 1
```

## Sample Data

The `fixtures/sample_data.py` file provides realistic test data:

### Sample Users
- Email/password user with hashed password
- OTP-only user
- Google OAuth user

### Sample Stories
- Complete stories with images
- Stories in progress
- Stories with different formats

### Sample Avatars
- Completed avatars with S3 URLs
- Avatars in progress
- Avatars with visual traits

### Mock API Responses
- OpenAI chat completion responses
- OpenAI image generation responses
- S3 upload responses
- Database query responses

## Test Coverage Goals

The test suite aims for:
- **80%+ Code Coverage**: Measured by pytest-cov
- **All API Endpoints**: Every FastAPI route tested
- **Error Scenarios**: Comprehensive error handling coverage
- **Integration Workflows**: Complete user journey testing

### Coverage Reports
```bash
# Generate HTML coverage report
make test-coverage

# View coverage report
open htmlcov/index.html
```

## Common Testing Patterns

### Testing Async Functions
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result is not None
```

### Testing API Endpoints
```python
def test_api_endpoint(test_client):
    response = test_client.post("/api/endpoint", json={"data": "test"})
    assert response.status_code == 200
    assert "expected_field" in response.json()
```

### Testing with Authentication
```python
def test_protected_endpoint(test_client, auth_headers):
    response = test_client.get("/protected", headers=auth_headers)
    assert response.status_code == 200
```

### Testing Database Operations
```python
@pytest.mark.asyncio
async def test_database_operation(mock_db_manager):
    mock_db_manager.execute_query.return_value = [{"id": 1}]
    result = await database_function()
    assert result is not None
```

## Debugging Tests

### Running Single Tests
```bash
# Run specific test function
cd src && python -m pytest ../tests/test_main.py::TestHealthEndpoints::test_health_endpoint -v

# Run with print statements
cd src && python -m pytest ../tests/test_main.py -v -s
```

### Test Debugging Tips
1. Use `pytest.set_trace()` for debugging
2. Check mock call arguments: `mock.assert_called_with(expected_args)`
3. Verify mock call counts: `assert mock.call_count == 2`
4. Use `caplog` fixture to check log messages

## Continuous Integration

The test suite is designed to run in CI/CD environments:

```bash
# CI command that installs deps and runs tests
make ci-test

# Linting and type checking
make ci-lint
```

### GitHub Actions
Tests automatically run on:
- Pull requests to main branch
- Pushes to main branch
- Manual workflow dispatch

## Contributing to Tests

### Adding New Tests
1. Follow existing naming conventions (`test_*`)
2. Use appropriate markers (`@pytest.mark.unit`, `@pytest.mark.integration`)
3. Include docstrings explaining test purpose
4. Mock external dependencies appropriately
5. Test both success and failure scenarios

### Test Best Practices
- **Arrange-Act-Assert**: Structure tests clearly
- **Single Responsibility**: One concept per test
- **Descriptive Names**: Test names should explain what they verify
- **Independent Tests**: Tests should not depend on each other
- **Mock External Calls**: Don't make real API calls in tests

### Example Test Structure
```python
@pytest.mark.asyncio
async def test_story_generation_with_avatar_success(self, mock_openai_client, mock_db_manager):
    """Test successful story generation with avatar integration."""
    # Arrange
    mock_db_manager.execute_query.return_value = [{"avatar_name": "Benny"}]
    mock_openai_client.chat.completions.create.return_value = mock_story_response
    
    # Act
    result = await generate_story_with_avatar("story prompt", user_id=1)
    
    # Assert
    assert result["title"] is not None
    assert "Benny" in result["story"]
    mock_openai_client.chat.completions.create.assert_called_once()
```

This comprehensive test suite ensures the My Story Buddy backend is reliable, maintainable, and bug-free!