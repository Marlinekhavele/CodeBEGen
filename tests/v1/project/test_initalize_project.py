from unittest.mock import patch

from app.api.v1.schemas.projects import ProjectInitResponse
from app.api.v1.services.projects import ProjectInitService
from conftest import TEST_BASE_URL

valid_payload = {
    "project_name": "Test Project",
    "language": "Python",
    "framework": "FastAPI"
}
invalid_payload = {}


def test_initialize_project_success(client):
    """Test project initialization success."""
    mock_response = ProjectInitResponse(
        project_id="12345",
        project_url="http://project.test.com",
        language="Python",
        framework="FastAPI"
    ).dict()

    with patch.object(
        ProjectInitService, "initialize_project", return_value=mock_response
    ):
        response = client.post(
            f"{TEST_BASE_URL}/api/v1/project-url/", json=valid_payload
        )

    assert (
        response.status_code == 201
    ), f"Unexpected status: {response.status_code}, Response: {response.json()}"
    expected_response = {
        "status_code": 201,
        "success": True,
        "message": "Project initialized successfully",
        "data": mock_response,
    }
    assert response.json() == expected_response


def test_initialize_project_invalid_request(client):
    """Test project initialization with missing required fields."""
    response = client.post(f"{TEST_BASE_URL}/api/v1/project-url/", json=invalid_payload)

    assert response.status_code == 422


def test_initialize_project_server_error(client):
    """Test project initialization when the service raises an error."""
    with patch.object(
        ProjectInitService,
        "initialize_project",
        side_effect=Exception("DB Connection Failed"),
    ):
        response = client.post(
            f"{TEST_BASE_URL}/api/v1/project-url/", json=valid_payload
        )

    assert response.status_code == 500
    assert response.json()["message"] == "Failed to initialize project"
    assert "DB Connection Failed" in response.json()["detail"]
