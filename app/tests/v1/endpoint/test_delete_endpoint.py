from unittest.mock import patch

from conftest import TEST_BASE_URL

PROJECT_ID = "new-test-project-6mm6x8"
ENDPOINT_PATH = "/v1/endpoint"


@patch(
    "app.api.v1.services.endpoints.EndpointService.delete_file",
    return_value={
        "project_id": PROJECT_ID,
        "endpoint_path": ENDPOINT_PATH,
        "file_path": "/path/to/deleted/file",
        "commit_hash": "abc123def456",
        "content_base64": None,
        "method": "GET",
        "message": "Endpoint deleted successfully",
        "description": "Deleted endpoint file",
    },
)
def test_delete_endpoint_file(mock_delete_file, client):
    """Test successful endpoint deletion"""
    params = {
        "project_id": PROJECT_ID,
        "endpoint_path": ENDPOINT_PATH,
        "method": "GET",
        "description": "Deleted endpoint file",
    }
    response = client.delete(f"{TEST_BASE_URL}/v1/endpoint", params=params)
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.json()}")
    assert response.status_code == 200
    assert "File deleted successfully" in response.json()["message"]

    # Verify correct parameters passed to service
    mock_delete_file.assert_called_once()
    request_arg = mock_delete_file.call_args[0][0]
    assert request_arg.project_id == PROJECT_ID
    assert request_arg.endpoint_path == ENDPOINT_PATH
    assert request_arg.method == "GET"


def test_delete_endpoint_file_invalid_request(client):
    """Test request with missing required parameters"""
    params = {
        "project_id": PROJECT_ID,
        # Missing endpoint_path and method
    }
    response = client.delete(f"{TEST_BASE_URL}/v1/endpoint", params=params)
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.json()}")
    assert response.status_code == 422
    error_details = response.json()["detail"]
    missing_params = [
        error["loc"][-1] for error in error_details if error["type"] == "missing"
    ]
    assert (
        "endpoint_path" in missing_params
    ), "endpoint_path should be reported as missing"
    assert "method" in missing_params, "method should be reported as missing"


@patch(
    "app.api.v1.services.endpoints.EndpointService.delete_file",
    side_effect=ValueError("Project with ID invalid_repo_url not found"),
)
def test_delete_endpoint_file_invalid_repo(mock_delete_file, client):
    """Test deletion with non-existent project"""
    params = {
        "project_id": "invalid_repo_url",
        "endpoint_path": ENDPOINT_PATH,
        "method": "GET",
        "description": "Invalid repo test",
    }
    response = client.delete(f"{TEST_BASE_URL}/v1/endpoint", params=params)
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.json()}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@patch(
    "app.api.v1.services.endpoints.EndpointService.delete_file",
    side_effect=Exception("Unexpected error"),
)
def test_delete_endpoint_file_server_error(mock_delete_file, client):
    """Test handling of unexpected server errors"""
    params = {
        "project_id": PROJECT_ID,
        "endpoint_path": ENDPOINT_PATH,
        "method": "GET",
        "description": "Server error test",
    }
    response = client.delete(f"{TEST_BASE_URL}/v1/endpoint", params=params)
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.json()}")
    assert response.status_code == 500
    assert "failed to delete file" in response.json()["message"].lower()

    # Additional logging for debugging
    print(f"Mock delete_file was called: {mock_delete_file.called}")
    if mock_delete_file.called:
        print(f"Mock delete_file call count: {mock_delete_file.call_count}")
        print(f"Mock delete_file call args: {mock_delete_file.call_args}")


@patch(
    "app.api.v1.services.endpoints.EndpointService.delete_file",
    return_value={
        "project_id": PROJECT_ID,
        "endpoint_path": ENDPOINT_PATH,
        "file_path": None,
        "commit_hash": None,
        "content_base64": None,
        "method": "GET",
        "message": "Endpoint not found: /v1/endpoint",
        "description": None,
    },
)
def test_delete_endpoint_not_found(mock_delete_file, client):
    """Test deletion of a non-existent endpoint"""
    params = {
        "project_id": PROJECT_ID,
        "endpoint_path": ENDPOINT_PATH,
        "method": "GET",
    }
    response = client.delete(f"{TEST_BASE_URL}/v1/endpoint", params=params)
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.json()}")

    assert response.status_code == 200
    assert "not found" in response.json()["data"]["message"].lower()
