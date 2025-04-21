import json

import pytest
from unittest import mock


import responses

from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

from app.api.v1.services.project_models import GetAllModels
from app.api.v1.routes.project_models import list_models
from config import settings
from main import app

# Create test client
client = TestClient(app)


# Tests for GetAllModels service
class TestGetAllModels:

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_all_models_success(self):
        # Mocking the API response for the repository contents
        project_id = "test-project"
        repo_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/models"

        models_data = [
            {
                "name": "model1.py",
                "path": "models/model1.py",
                "type": "file",
                "url": f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/models/model1.py",
                "html_url": f"https://example.com/{project_id}/models/model1.py",
                "size": 1000
            },
            {
                "name": "model2.py",
                "path": "models/model2.py",
                "type": "file",
                "url": f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/models/model2.py",
                "html_url": f"https://example.com/{project_id}/models/model2.py",
                "size": 2000
            },
            {
                "name": "__init__.py",  # Should be filtered out
                "path": "models/__init__.py",
                "type": "file",
                "url": f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/models/__init__.py",
                "html_url": f"https://example.com/{project_id}/models/__init__.py",
                "size": 100
            }
        ]

        responses.add(
            responses.GET,
            repo_url,
            json=models_data,
            status=200
        )

        # Mock individual file responses
        for model in models_data:
            if model["name"] not in ["__init__.py"]:
                responses.add(
                    responses.GET,
                    model["url"],
                    json={"content": "dummy content"},
                    status=200
                )

        result = await GetAllModels.get_all_models_from_repo(project_id)

        assert len(result) == 2
        assert result[0]["name"] == "model1"
        assert result[1]["name"] == "model2"

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_all_models_404(self):
        # Test when models directory doesn't exist
        project_id = "nonexistent-project"
        repo_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/models"

        responses.add(
            responses.GET,
            repo_url,
            json={"message": "Not Found"},
            status=404
        )

        result = await GetAllModels.get_all_models_from_repo(project_id)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 404

        content = result.body.decode()
        assert "Models directory not found" in content

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_all_models_server_error(self):
        # Test server error response
        project_id = "error-project"
        repo_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/models"

        responses.add(
            responses.GET,
            repo_url,
            json={"message": "Internal Server Error"},
            status=500
        )

        result = await GetAllModels.get_all_models_from_repo(project_id)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 500

        content = result.body.decode()
        assert "Failed to fetch models" in content


# Tests for the API endpoint
class TestModelRoutes:

    @pytest.mark.asyncio
    async def test_list_models_success(self, mock_get_all_models):
        # Set up mock return value
        models = [
            {
                "name": "model1",
                "path": "models/model1.py",
                "url": "https://example.com/model1.py",
                "size": 1000
            },
            {
                "name": "model2",
                "path": "models/model2.py",
                "url": "https://example.com/model2.py",
                "size": 2000
            }
        ]
        mock_get_all_models.return_value = models

        response = await list_models("test-project")

        assert isinstance(response, JSONResponse)
        assert response.status_code == 200

        content = json.loads(response.body.decode())
        assert content["message"] == "Models Retrieved Successfully"
        assert len(content["data"]) == 2
        assert content["data"][0]["name"] == "model1"
        assert content["data"][1]["name"] == "model2"

    @pytest.mark.asyncio
    async def test_list_models_value_error(self, mock_get_all_models):
        mock_get_all_models.side_effect = ValueError("Models not found")

        response = await list_models("nonexistent-project")

        assert isinstance(response, JSONResponse)
        assert response.status_code == 404

        content = json.loads(response.body.decode())
        assert content["message"] == "Models not found"
        assert "Models not found" in content["detail"]

    @pytest.mark.asyncio
    async def test_list_models_exception(self, mock_get_all_models):
        mock_get_all_models.side_effect = Exception("Unexpected error")

        response = await list_models("error-project")

        assert isinstance(response, JSONResponse)
        assert response.status_code == 500

        content = json.loads(response.body.decode())
        assert content["message"] == "Error retrieving models"
        assert "Unexpected error" in content["detail"]


# Integration test with the FastAPI test client
def test_list_models_endpoint_with_client(mock_get_all_models):
    # Set up mock return value
    models = [
        {
            "name": "model1",
            "path": "models/model1.py",
            "url": "https://example.com/model1.py",
            "size": 1000
        },
        {
            "name": "model2",
            "path": "models/model2.py",
            "url": "https://example.com/model2.py",
            "size": 2000
        }
    ]
    mock_get_all_models.return_value = models

    response = client.get("/api/v1/projects/test-project/models/")

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["message"] == "Models Retrieved Successfully"
    assert len(response_data["data"]) == 2
    assert response_data["data"][0]["name"] == "model1"