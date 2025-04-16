import asyncio

import pytest
from fastapi.testclient import TestClient

from main import app

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
