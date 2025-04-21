import json
import pytest
from unittest import mock
import responses
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse
from app.api.v1.services.project_schemas import GetAllSchemas  
from app.api.v1.routes.project_schemas import list_schemas  
from config import settings
from main import app

client = TestClient(app)

class TestGetAllSchemas:

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_all_schemas_success(self):
        project_id = "test-project"
        repo_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/schemas"

        schemas_data = [
            {
                "name": "schema1.py", 
                "path": "schemas/schema1.py", 
                "type": "file",
                "url": f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/schemas/schema1.py",
                "html_url": f"https://example.com/{project_id}/schemas/schema1.py",
                "size": 1000
            },
            {
                "name": "schema2.py",  
                "path": "schemas/schema2.py",
                "type": "file",
                "url": f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/schemas/schema2.py", # Changed to .py
                "html_url": f"https://example.com/{project_id}/schemas/schema2.py",
                "size": 2000
            },
            {
                "name": "__init__.py", 
                "path": "schemas/__init__.py",
                "type": "file",
                "url": f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/schemas/__init__.py",
                "html_url": f"https://example.com/{project_id}/schemas/__init__.py",
                "size": 100
            }
        ]

        responses.add(
            responses.GET,
            repo_url,
            json=schemas_data,
            status=200
        )

        # Mock individual file responses
        for schema in schemas_data:
            if schema["name"] not in ["__init__.py"]:
                responses.add(
                    responses.GET,
                    schema["url"],
                    json={"content": "dummy content"},
                    status=200
                )

        result = await GetAllSchemas.get_all_schemas_from_repo(project_id)

        assert len(result) == 2
        assert result[0]["name"] == "schema1"
        assert result[1]["name"] == "schema2"

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_all_schemas_404(self):
        # Test when schemas directory doesn't exist
        project_id = "nonexistent-project"
        repo_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/schemas"

        responses.add(
            responses.GET,
            repo_url,
            json={"message": "Not Found"},
            status=404
        )

        result = await GetAllSchemas.get_all_schemas_from_repo(project_id)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 404

        content = result.body.decode()
        assert "Schemas directory not found" in content

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_all_schemas_server_error(self):
        project_id = "error-project"
        repo_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/schemas"

        responses.add(
            responses.GET,
            repo_url,
            json={"message": "Internal Server Error"},
            status=500
        )

        result = await GetAllSchemas.get_all_schemas_from_repo(project_id)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 500

        content = result.body.decode()
        assert "Failed to fetch schemas" in content


class TestSchemaRoutes:

    @pytest.mark.asyncio
    async def test_list_schemas_success(self, mock_get_all_schemas):
        # Set up mock return value
        schemas = [
            {
                "name": "schema1",
                "path": "schemas/schema1.json",
                "url": "https://example.com/schema1.json",
                "size": 1000
            },
            {
                "name": "schema2",
                "path": "schemas/schema2.json",
                "url": "https://example.com/schema2.json",
                "size": 2000
            }
        ]
        mock_get_all_schemas.return_value = schemas

        response = await list_schemas("test-project")

        assert isinstance(response, JSONResponse)
        assert response.status_code == 200

        content = json.loads(response.body.decode())
        assert content["message"] == "Schemas Retrieved Successfully"
        assert len(content["data"]) == 2
        assert content["data"][0]["name"] == "schema1"
        assert content["data"][1]["name"] == "schema2"

    @pytest.mark.asyncio
    async def test_list_schemas_value_error(self, mock_get_all_schemas):
        mock_get_all_schemas.side_effect = ValueError("Schemas not found")

        response = await list_schemas("nonexistent-project")

        assert isinstance(response, JSONResponse)
        assert response.status_code == 404

        content = json.loads(response.body.decode())
        assert content["message"] == "Schemas not found"
        assert "Schemas not found" in content["detail"]

    @pytest.mark.asyncio
    async def test_list_schemas_exception(self, mock_get_all_schemas):
        mock_get_all_schemas.side_effect = Exception("Unexpected error")

        response = await list_schemas("error-project")

        assert isinstance(response, JSONResponse)
        assert response.status_code == 500

        content = json.loads(response.body.decode())
        assert content["message"] == "Error retrieving schemas"
        assert "Unexpected error" in content["detail"]

