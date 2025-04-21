import asyncio
from unittest import mock
import pytest
from fastapi.testclient import TestClient
from main import app

from app.api.v1.services.project_helpers import GetAllHelpers
from app.api.v1.services.project_models import GetAllModels
from app.api.v1.services.project_schemas import GetAllSchemas

TEST_BASE_URL = "http://test"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client():
    """Fixture that provides a TestClient instance."""
    return TestClient(app)


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Fixture to set up any test database or test state before each test."""
    # Setup test database or state here
    yield
    # Cleanup test database or state here

# Mocks for helpers
@pytest.fixture
def mock_get_all_helpers():
    """Mock the get_all_helpers_from_repo method."""
    with mock.patch.object(GetAllHelpers, 'get_all_helpers_from_repo') as _mock:
        yield _mock

@pytest.fixture
def mock_get_helper_content():
    """Mock the get_helper_content_from_repo method."""
    with mock.patch.object(GetAllHelpers, 'get_helper_content_from_repo') as _mock:
        yield _mock

# Mocks for models
@pytest.fixture
def mock_get_all_models():
    """Mock the get_all_models_from_repo method."""
    with mock.patch.object(GetAllModels, 'get_all_models_from_repo') as _mock:
        yield _mock

@pytest.fixture
def mock_get_model_content():
    """Mock the get_model_content_from_repo method."""
    with mock.patch.object(GetAllModels, 'get_model_content_from_repo') as _mock:
        yield _mock

# Mocks for schemas
@pytest.fixture
def mock_get_all_schemas():
    """Mock the get_all_schemas_from_repo method."""
    with mock.patch.object(GetAllSchemas, 'get_all_schemas_from_repo') as _mock:
        yield _mock

@pytest.fixture
def mock_get_schema_content():
    """Mock the get_schema_content_from_repo method."""
    with mock.patch.object(GetAllSchemas, 'get_schema_content_from_repo') as _mock:
        yield _mock
