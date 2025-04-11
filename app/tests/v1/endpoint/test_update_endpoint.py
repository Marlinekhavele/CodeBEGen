import base64
from unittest.mock import patch

from fastapi.testclient import TestClient

from conftest import TEST_BASE_URL
from main import app

client = TestClient(app)

ENDPOINT_URL = "/v1/endpoint"
PROJECT_ID = "new-test-project-6mm6x8"
ENDPOINT_PATH = "/v1/endpoint"
UPDATED_FILE_CONTENT = "print('Welcome to CodeBegen Projects!')"
FILE_CONTENT_BASE64 = base64.b64encode(UPDATED_FILE_CONTENT.encode()).decode()


@patch("app.api.v1.services.endpoints.EndpointService.update_file")
def test_update_endpoint(mock_update_file):
    """
    Test updating an endpoint file with valid data.
    """
    mock_update_file.return_value = {
        "project_id": PROJECT_ID,
        "endpoint_path": ENDPOINT_PATH,
        "file_path": "/path/to/updated/file",
        "content_base64": FILE_CONTENT_BASE64,
        "commit_hash": "abc123def456",
        "file_hash": "abcdef123456",  # Add file_hash
        "method": "GET",  # Add method
        "message": "File updated successfully",
        "description": "Updated endpoint file",
    }

    response = client.put(
        ENDPOINT_URL,
        json={
            "project_id": PROJECT_ID,
            "endpoint_path": ENDPOINT_PATH,
            "content_base64": FILE_CONTENT_BASE64,
            "method": "GET",
            "description": "New endpoint file",
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "File updated successfully"


@patch("app.api.v1.services.endpoints.EndpointService.update_file")
def test_update_endpoint_invalid_request(mock_update_file):
    """
    Test updating an endpoint file with missing required fields.
    """
    response = client.put(
        ENDPOINT_URL,
        json={
            "project_id": PROJECT_ID,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "endpoint_path"]


@patch(
    "app.api.v1.services.endpoints.EndpointService.update_file",
    side_effect=ValueError("Invalid repository"),
)
def test_update_endpoint_invalid_repository(mock_update_file):
    """
    Test updating an endpoint file with an invalid repo URL.
    """
    response = client.put(
        ENDPOINT_URL,
        json={
            "project_id": "invalid_url",
            "endpoint_path": ENDPOINT_PATH,
            "content_base64": FILE_CONTENT_BASE64,
            "method": "GET",
            "description": "New endpoint file",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Invalid repository"


@patch(
    "app.api.v1.services.endpoints.EndpointService.update_file",
    side_effect=Exception("Unexpected error"),
)
def test_update_endpoint_file_server_error(mock_update_file, client):
    """
    Test unexpected internal server error when updating an endpoint file.
    """
    # Define the request payload
    payload = {
        "project_id": PROJECT_ID,
        "endpoint_path": ENDPOINT_PATH,
        "content_base64": FILE_CONTENT_BASE64,
        "method": "GET",
        "description": "New endpoint file",
    }

    # Make the PUT request
    response = client.put(
        f"{TEST_BASE_URL}/v1/endpoint",
        json=payload,
    )

    # Assert the response status code is 500 (Internal Server Error)
    assert response.status_code == 500, (
        f"Expected status code 500, but got {response.status_code}. "
        f"Response: {response.json()}"
    )

    # Assert the response message
    assert (
        response.json()["message"] == "Failed to update file"
    ), f"Expected message 'Failed to update file', but got {response.json()['message']}"

    # Assert the error detail contains the expected error message
    assert (
        "Unexpected error" in response.json()["detail"]
    ), f"Expected 'Unexpected error' in detail, but got {response.json()['detail']}"
