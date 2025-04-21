import base64
import json
from unittest import mock

import pytest
import responses
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.api.v1.routes.project_models import get_model_content
from app.api.v1.services.project_models import GetAllModels
from config import settings
from main import app

# Create test client
client = TestClient(app)


# Tests for get_model_content_from_repo method
class TestGetModelContent:

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_model_content_success(self):
        # Mocking the API response for the model content
        project_id = "test-project"
        model_name = "test_model"
        model_file = "test_model.py"

        model_content = "def test_function():\n    return 'Hello, world!'"

        encoded_content = base64.b64encode(model_content.encode()).decode()

        repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/models/{model_file}"

        # Create mock response data with base64 encoded content
        response_data = {
            "name": model_file,
            "path": f"models/{model_file}",
            "content": encoded_content,
            "encoding": "base64",
            "url": repo_api_url,
            "html_url": f"https://example.com/{project_id}/models/{model_file}",
            "size": len(model_content),
        }

        responses.add(responses.GET, repo_api_url, json=response_data, status=200)

        result = await GetAllModels.get_model_content_from_repo(project_id, model_name)

        assert isinstance(result, dict)
        assert result["name"] == model_name
        assert result["format"] == "text"
        assert result["content"] == model_content
        assert result["content_base64"] == encoded_content

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_model_content_with_extension(self):
        # Test with model name that includes .py extension
        project_id = "test-project"
        model_name = "test_model.py"
        expected_model_name = "test_model"  # Should be returned without extension

        model_content = "def another_test():\n    pass"
        encoded_content = base64.b64encode(model_content.encode()).decode()

        repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/models/{model_name}"

        response_data = {
            "name": model_name,
            "path": f"models/{model_name}",
            "content": encoded_content,
            "encoding": "base64",
            "url": repo_api_url,
            "html_url": f"https://example.com/{project_id}/models/{model_name}",
            "size": len(model_content),
        }

        responses.add(responses.GET, repo_api_url, json=response_data, status=200)

        result = await GetAllModels.get_model_content_from_repo(project_id, model_name)

        assert result["name"] == expected_model_name
        assert result["content"] == model_content

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_model_content_404(self):
        # Test when model doesn't exist
        project_id = "test-project"
        model_name = "nonexistent_model"

        repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/models/{model_name}.py"

        responses.add(
            responses.GET, repo_api_url, json={"message": "Not Found"}, status=404
        )

        result = await GetAllModels.get_model_content_from_repo(project_id, model_name)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 404
        content = result.body.decode()
        assert f"Model {model_name} not found in project {project_id}" in content

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_model_content_server_error(self):
        # Test server error response
        project_id = "test-project"
        model_name = "error_model"

        repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/models/{model_name}.py"

        responses.add(
            responses.GET,
            repo_api_url,
            json={"message": "Internal Server Error"},
            status=500,
        )

        result = await GetAllModels.get_model_content_from_repo(project_id, model_name)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 500
        content = result.body.decode()
        assert "Failed to fetch model content" in content


# Tests for API endpoint
class TestModelContentEndpoint:

    @pytest.mark.asyncio
    async def test_get_model_content_success(self, mock_get_all_models):
        # Set up mock return value for successful model content retrieval
        model_content = {
            "name": "test_model",
            "format": "text",
            "content": "def test_function():\n    return 'Hello, world!'",
            "content_base64": "ZGVmIHRlc3RfZnVuY3Rpb24oKToKICAgIHJldHVybiAnSGVsbG8sIHdvcmxkISc=",
        }

        # Mock the service method
        with mock.patch(
            "app.api.v1.services.project_models.GetAllModels.get_model_content_from_repo"
        ) as mock_get_content:
            mock_get_content.return_value = model_content

            response = await get_model_content("test-project", "test_model")

            assert isinstance(response, JSONResponse)
            assert response.status_code == 200

            content = json.loads(response.body.decode())
            assert content["message"] == "Model Content Retrieved Successfully"
            assert content["data"]["name"] == "test_model"
            assert content["data"]["format"] == "text"
            assert "content" in content["data"]
            assert "content_base64" in content["data"]

    @pytest.mark.asyncio
    async def test_get_model_content_not_found(self):
        # Test when model not found
        error_response = JSONResponse(
            status_code=404,
            content={
                "status_code": 404,
                "message": "Model test_model not found in project test-project",
                "detail": "The specified model does not exist in this repository",
            },
        )

        # Mock the service method to return an error response
        with mock.patch(
            "app.api.v1.services.project_models.GetAllModels.get_model_content_from_repo"
        ) as mock_get_content:
            mock_get_content.return_value = error_response

            response = await get_model_content("test-project", "test_model")

            assert response == error_response
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_model_content_exception(self):
        # Mock the service method to raise an exception
        with mock.patch(
            "app.api.v1.services.project_models.GetAllModels.get_model_content_from_repo"
        ) as mock_get_content:
            mock_get_content.side_effect = Exception("Unexpected error")

            response = await get_model_content("test-project", "test_model")

            assert isinstance(response, JSONResponse)
            assert response.status_code == 500

            content = json.loads(response.body.decode())
            assert content["message"] == "Error retrieving model content"
            assert "Unexpected error" in content["detail"]


# Integration test with the FastAPI test client
def test_get_model_content_endpoint_with_client():
    # Test the endpoint using TestClient
    model_content = {
        "name": "test_model",
        "format": "text",
        "content": "def test_function():\n    return 'Hello, world!'",
        "content_base64": "ZGVmIHRlc3RfZnVuY3Rpb24oKToKICAgIHJldHVybiAnSGVsbG8sIHdvcmxkISc=",
    }

    # Mock the service method
    with mock.patch(
        "app.api.v1.services.project_models.GetAllModels.get_model_content_from_repo"
    ) as mock_get_content:
        mock_get_content.return_value = model_content

        response = client.get("/api/v1/projects/test-project/models/test_model/content")

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["message"] == "Model Content Retrieved Successfully"
        assert response_data["data"]["name"] == "test_model"
        assert "content" in response_data["data"]
        assert "content_base64" in response_data["data"]
