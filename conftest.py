import pytest
from fastapi.testclient import TestClient
from main import app

TEST_BASE_URL = "http://test"

@pytest.fixture
def client():
    """Fixture that provides a TestClient instance."""
    return TestClient(app)



