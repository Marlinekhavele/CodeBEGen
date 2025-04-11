import base64
from unittest.mock import patch

from fastapi.testclient import TestClient

from conftest import TEST_BASE_URL
from main import app

client = TestClient(app)

ENDPOINT_URL = "/v1/endpoint"
PROJECT_ID = "new-test-project-6mm6x8"
ENDPOINT_PATH = "/v1/endpoint"
FILE_CONTENT = "print('Hello World!')"
FILE_CONTENT_BASE64 = base64.b64encode(FILE_CONTENT.encode()).decode()


@patch("app.api.v1.services.endpoints.EndpointService.get_file")
def test_get_endpoint_file(mock_get_file):
    """
    Test getting an endpoint file with valid parameters.
    """
    mock_get_file.return_value = {
        "project_id": PROJECT_ID,
        "endpoint_path": ENDPOINT_PATH,
        "file_path": "/path/to/file.py",
        "content_base64": FILE_CONTENT_BASE64,
        "method": "GET",
        "file_hash": "abcdef123456",
        "message": "File retrieved successfully",
        "description": "Endpoint file",
    }

    response = client.get(
        f"{ENDPOINT_URL}?project_id={PROJECT_ID}&endpoint_path={ENDPOINT_PATH}&method=GET"
    )

    assert response.status_code == 200
    assert response.json()["message"] == "File retrieved successfully"
    assert response.json()["data"]["content_base64"] == FILE_CONTENT_BASE64


@patch("app.api.v1.services.endpoints.EndpointService.get_file")
def test_get_endpoint_file_missing_parameters(mock_get_file):
    """
    Test getting an endpoint file with missing required parameters.
    """
    response = client.get(
        f"{ENDPOINT_URL}?project_id={PROJECT_ID}"  # Missing endpoint_path and method
    )

    assert response.status_code == 422
    assert "endpoint_path" in str(response.json())
    assert "method" in str(response.json())


@patch(
    "app.api.v1.services.endpoints.EndpointService.get_file",
    side_effect=ValueError("Endpoint not found"),
)
def test_get_endpoint_file_not_found(mock_get_file):
    """
    Test getting a non-existent endpoint file.
    """
    response = client.get(
        f"{ENDPOINT_URL}?project_id={PROJECT_ID}&endpoint_path=non_existent_path&method=GET"
    )

    assert response.status_code == 404
    assert response.json()["message"] == "File not found"
    assert "Endpoint not found" in response.json()["detail"]


@patch(
    "app.api.v1.services.endpoints.EndpointService.get_file",
    side_effect=Exception("Unexpected error"),
)
def test_get_endpoint_file_server_error(mock_get_file):
    """
    Test server error when getting an endpoint file.
    """
    response = client.get(
        f"{TEST_BASE_URL}/v1/endpoint?project_id={PROJECT_ID}&endpoint_path={ENDPOINT_PATH}&method=GET"
    )

    assert response.status_code == 500, (
        f"Expected status code 500, but got {response.status_code}. "
        f"Response: {response.json()}"
    )
    assert response.json()["message"] == "Failed to retrieve file"
    assert "Unexpected error" in response.json()["detail"]
