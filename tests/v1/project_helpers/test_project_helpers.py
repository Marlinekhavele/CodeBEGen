import json

import pytest
import responses
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.api.v1.routes.project_helpers import list_helpers
from app.api.v1.services.project_helpers import GetAllHelpers
from config import settings
from main import app

# Create test client
client = TestClient(app)


class TestGetAllHelpers:

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_all_helpers_success(self):
        # Mocking the API response for the repository contents
        project_id = "test-project"
        repo_url = (
            f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/helpers"
        )

        helpers_data = [
            {
                "name": "data_helper.py",
                "path": "helpers/data_helper.py",
                "type": "file",
                "url": f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/helpers/data_helper.py",
                "html_url": f"https://example.com/{project_id}/helpers/data_helper.py",
                "size": 1000,
            },
            {
                "name": "deployment_helper.sh",
                "path": "helpers/deployment_helper.sh",
                "type": "file",
                "url": f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/helpers/deployment_helper.sh",
                "html_url": f"https://example.com/{project_id}/helpers/deployment_helper.sh",
                "size": 2000,
            },
            {
                "name": "__init__.py",  # Should be filtered out
                "path": "helpers/__init__.py",
                "type": "file",
                "url": f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/helpers/__init__.py",
                "html_url": f"https://example.com/{project_id}/helpers/__init__.py",
                "size": 100,
            },
        ]

        responses.add(responses.GET, repo_url, json=helpers_data, status=200)

        # Mock individual file responses
        for helper in helpers_data:
            if helper["name"] not in ["__init__.py"]:
                responses.add(
                    responses.GET,
                    helper["url"],
                    json={"content": "dummy content"},
                    status=200,
                )

        result = await GetAllHelpers.get_all_helpers_from_repo(project_id)

        assert len(result) == 2
        assert result[0]["name"] == "data_helper"
        assert result[0]["type"] == "python"
        assert result[1]["name"] == "deployment_helper"
        assert result[1]["type"] == "shell"

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_all_helpers_404(self):
        # Test when helpers directory doesn't exist
        project_id = "nonexistent-project"
        repo_url = (
            f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/helpers"
        )

        responses.add(
            responses.GET, repo_url, json={"message": "Not Found"}, status=404
        )

        result = await GetAllHelpers.get_all_helpers_from_repo(project_id)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 404

        content = result.body.decode()
        assert "Helpers directory not found" in content

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_all_helpers_server_error(self):
        project_id = "error-project"
        repo_url = (
            f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/helpers"
        )

        responses.add(
            responses.GET,
            repo_url,
            json={"message": "Internal Server Error"},
            status=500,
        )

        result = await GetAllHelpers.get_all_helpers_from_repo(project_id)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 500

        content = result.body.decode()
        assert "Failed to fetch helpers" in content


class TestHelperRoutes:

    @pytest.mark.asyncio
    async def test_list_helpers_success(self, mock_get_all_helpers):
        # Set up mock return value
        helpers = [
            {
                "name": "data_helper",
                "path": "helpers/data_helper.py",
                "url": "https://example.com/data_helper.py",
                "size": 1000,
                "type": "python",
            },
            {
                "name": "deployment_helper",
                "path": "helpers/deployment_helper.sh",
                "url": "https://example.com/deployment_helper.sh",
                "size": 2000,
                "type": "shell",
            },
        ]
        mock_get_all_helpers.return_value = helpers

        response = await list_helpers("test-project")

        assert isinstance(response, JSONResponse)
        assert response.status_code == 200

        content = json.loads(response.body.decode())
        assert content["message"] == "Helpers Retrieved Successfully"
        assert len(content["data"]) == 2
        assert content["data"][0]["name"] == "data_helper"
        assert content["data"][1]["name"] == "deployment_helper"

    @pytest.mark.asyncio
    async def test_list_helpers_value_error(self, mock_get_all_helpers):
        mock_get_all_helpers.side_effect = ValueError("Helpers not found")

        response = await list_helpers("nonexistent-project")

        assert isinstance(response, JSONResponse)
        assert response.status_code == 404

        content = json.loads(response.body.decode())
        assert content["message"] == "Helpers not found"
        assert "Helpers not found" in content["detail"]

    @pytest.mark.asyncio
    async def test_list_helpers_exception(self, mock_get_all_helpers):
        mock_get_all_helpers.side_effect = Exception("Unexpected error")

        response = await list_helpers("error-project")

        assert isinstance(response, JSONResponse)
        assert response.status_code == 500

        content = json.loads(response.body.decode())
        assert content["message"] == "Error retrieving helpers"
        assert "Unexpected error" in content["detail"]
