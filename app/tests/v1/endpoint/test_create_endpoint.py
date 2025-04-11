import base64
import pytest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

# Test data
PROJECT_ID = "new-test-project-6mm6x8"
ENDPOINT_PATH = "/v1/endpoint"
FILE_CONTENT = "print('Hello World!')"
FILE_CONTENT_BASE64 = base64.b64encode(FILE_CONTENT.encode()).decode()


@patch(
    "app.api.v1.services.endpoints.EndpointService.create_endpoint",
    return_value={
        "project_id": PROJECT_ID,
        "endpoint_path": ENDPOINT_PATH,
        "file_path": "/v1/endpoint.py",
        "content_base64": FILE_CONTENT_BASE64,
        "method": "POST",
        "commit_hash": "abc123def456",
        "file_hash": "abcdef123456",  # Add file_hash
        "message": "File created successfully",
        "description": "New endpoint file", 
    },
)
def test_create_endpoint_file(mock_create_endpoint):
    """
    Test creating a new endpoint file.
    """
    payload = {
        "project_id": PROJECT_ID,
        "endpoint_path": ENDPOINT_PATH,
        "content_base64": FILE_CONTENT_BASE64,
        "method": "POST",
        "description": "New endpoint file", 

    }
    response = client.post("/v1/endpoint", json=payload)

    assert response.status_code in [
        201,
        200,
    ], f"Unexpected status: {response.status_code}, Response: {response.json()}"
    assert response.json()["message"] == "File created successfully"


def test_create_endpoint_file_invalid_method():
    """
    Test creating an endpoint file with invalid HTTP method.
    """
    payload = {
        "project_id": PROJECT_ID,
        "endpoint_path": ENDPOINT_PATH,
        "content_base64": FILE_CONTENT_BASE64,
        "method": "INVALID",
        "description": "New endpoint file", 

    }
    response = client.post("/v1/endpoint", json=payload)
    assert response.status_code == 422


@patch(
    "app.api.v1.services.endpoints.get_project_dir_from_repo_url",
    side_effect=ValueError("Invalid repository"),
)
def test_create_endpoint_file_invalid_repo(mock_project_dir):
    """
    Test creating an endpoint file with an invalid repo URL.
    """
    payload = {
        "project_id": "invalid_repo_url",  # Invalid repo
        "endpoint_path": ENDPOINT_PATH,
        "content_base64": FILE_CONTENT_BASE64,
        "method": "POST",
        "description": "New endpoint file", 

    }
    response = client.post("/v1/endpoint", json=payload)

    assert (
        response.status_code == 404
    ), f"Unexpected status: {response.status_code}, Response: {response.json()}"
    assert response.json()["detail"] == "Invalid repository"


@patch(
    "app.api.v1.services.endpoints.EndpointService.create_endpoint",
    side_effect=Exception("Unexpected error"),
)
def test_create_endpoint_file_server_error(mock_create_file):
    """
    Test unexpected internal server error when creating an endpoint file.
    """
    payload = {
        "project_id": PROJECT_ID,
        "endpoint_path": ENDPOINT_PATH,
        "content_base64": FILE_CONTENT_BASE64,
        "method": "POST",
        "description": "New endpoint file",


    }
    response = client.post("/v1/endpoint", json=payload)

    assert (
        response.status_code == 500
    ), f"Unexpected status: {response.status_code}, Response: {response.json()}"
    assert "Failed to create file" in response.json()["message"]
