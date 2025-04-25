import json

import pytest
import responses
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.api.v1.routes.project_docs import list_docs
from app.api.v1.services.project_docs import GetAllDocs
from config import settings
from main import app

# Create test client
client = TestClient(app)


class TestGetAllDocs:

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_all_docs_success(self):
        # Mocking the API response for the repository contents
        project_id = "test-project"
        repo_url = (
            f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/docs"
        )

        docs_data = [
            {
                "name": "readme.md",
                "path": "docs/readme.md",
                "type": "file",
                "url": f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/docs/readme.md",
                "html_url": f"https://example.com/{project_id}/docs/readme.md",
                "size": 1000,
            },
            {
                "name": "api_reference.md",
                "path": "docs/api_reference.md",
                "type": "file",
                "url": f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/docs/api_reference.md",
                "html_url": f"https://example.com/{project_id}/docs/api_reference.md",
                "size": 2000,
            },
            {
                "name": "__init__.py",  # Should be filtered out
                "path": "docs/__init__.py",
                "type": "file",
                "url": f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/docs/__init__.py",
                "html_url": f"https://example.com/{project_id}/docs/__init__.py",
                "size": 100,
            },
        ]

        responses.add(responses.GET, repo_url, json=docs_data, status=200)

        # Mock individual file responses
        for doc in docs_data:
            if doc["name"] not in ["__init__.py"]:
                responses.add(
                    responses.GET,
                    doc["url"],
                    json={"content": "dummy content"},
                    status=200,
                )

        result = await GetAllDocs.get_all_docs_from_repo(project_id)

        # Fix: Check the length of result["data"]
        assert len(result["data"]) == 2
        assert result["data"][0]["name"] == "readme"
        assert result["data"][0]["type"] == "markdown"
        assert result["data"][1]["name"] == "api_reference"
        assert result["data"][1]["type"] == "markdown"

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_all_docs_404(self):
        # Test when docs directory doesn't exist
        project_id = "nonexistent-project"
        repo_url = (
            f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/docs"
        )

        responses.add(
            responses.GET, repo_url, json={"message": "Not Found"}, status=404
        )

        result = await GetAllDocs.get_all_docs_from_repo(project_id)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 404

        content = result.body.decode()
        assert "Docs directory not found" in content

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_all_docs_server_error(self):
        project_id = "error-project"
        repo_url = (
            f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/docs"
        )

        responses.add(
            responses.GET,
            repo_url,
            json={"message": "Internal Server Error"},
            status=500,
        )

        result = await GetAllDocs.get_all_docs_from_repo(project_id)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 500

        content = result.body.decode()
        assert "Failed to fetch docs" in content


class TestDocsRoutes:

    @pytest.mark.asyncio
    async def test_list_docs_success(self, mock_get_all_docs):
        # Set up mock return value
        docs = [
            {
                "name": "readme",
                "path": "docs/readme.md",
                "url": "https://example.com/readme.md",
                "size": 1000,
                "type": "markdown",
            },
            {
                "name": "api_reference",
                "path": "docs/api_reference.md",
                "url": "https://example.com/api_reference.md",
                "size": 2000,
                "type": "markdown",
            },
        ]
        mock_get_all_docs.return_value = docs

        response = await list_docs("test-project")

        assert isinstance(response, JSONResponse)
        assert response.status_code == 200

        content = json.loads(response.body.decode())
        # Fix: Update expected message
        assert content["message"] == "Documentation Retrieved Successfully"
        assert len(content["data"]) == 2
        assert content["data"][0]["name"] == "readme"
        assert content["data"][1]["name"] == "api_reference"

    @pytest.mark.asyncio
    async def test_list_docs_value_error(self, mock_get_all_docs):
        mock_get_all_docs.side_effect = ValueError("Docs not found")

        response = await list_docs("nonexistent-project")

        assert isinstance(response, JSONResponse)
        assert response.status_code == 404

        content = json.loads(response.body.decode())
        # Fix: Update expected message
        assert content["message"] == "Documentation not found"
        assert "Docs not found" in content["detail"]

    @pytest.mark.asyncio
    async def test_list_docs_exception(self, mock_get_all_docs):
        mock_get_all_docs.side_effect = Exception("Unexpected error")

        response = await list_docs("error-project")

        assert isinstance(response, JSONResponse)
        assert response.status_code == 500

        content = json.loads(response.body.decode())
        # Fix: Update expected message
        assert content["message"] == "Error retrieving documentation"
        assert "Unexpected error" in content["detail"]