import base64

import pytest
import responses
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.api.v1.services.project_schemas import GetAllSchemas
from config import settings
from main import app

# Create test client
client = TestClient(app)


class TestGetSchemaContent:

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_schema_content_success(self):
        project_id = "test-project"
        schema_name = "test_schema"
        schema_file = "test_schema.py"

        schema_content = "def test_function():\n    return 'Hello, world!'"

        encoded_content = base64.b64encode(schema_content.encode()).decode()

        repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/schemas/{schema_file}"

        response_data = {
            "name": schema_file,
            "path": f"schemas/{schema_file}",
            "content": encoded_content,
            "encoding": "base64",
            "url": repo_api_url,
            "html_url": f"https://example.com/{project_id}/schemas/{schema_file}",
            "size": len(schema_content),
        }

        responses.add(responses.GET, repo_api_url, json=response_data, status=200)

        result = await GetAllSchemas.get_schema_content_from_repo(
            project_id, schema_name
        )

        assert isinstance(result, dict)
        assert result["name"] == schema_name
        assert result["format"] == "text"
        assert result["content"] == schema_content
        assert result["content_base64"] == encoded_content

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_schema_content_with_extension(self):
        project_id = "test-project"
        schema_name = "test_schema.py"
        expected_schema_name = "test_schema"

        schema_content = "def another_test():\n    pass"
        encoded_content = base64.b64encode(schema_content.encode()).decode()

        repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/schemas/{schema_name}"

        response_data = {
            "name": schema_name,
            "path": f"schemas/{schema_name}",
            "content": encoded_content,
            "encoding": "base64",
            "url": repo_api_url,
            "html_url": f"https://example.com/{project_id}/schemas/{schema_name}",
            "size": len(schema_content),
        }

        responses.add(responses.GET, repo_api_url, json=response_data, status=200)

        result = await GetAllSchemas.get_schema_content_from_repo(
            project_id, schema_name
        )

        assert result["name"] == expected_schema_name
        assert result["content"] == schema_content

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_schema_content_404(self):
        # Test when schema doesn't exist
        project_id = "test-project"
        schema_name = "nonexistent_schema"

        repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/schemas/{schema_name}.py"

        responses.add(
            responses.GET, repo_api_url, json={"message": "Not Found"}, status=404
        )

        result = await GetAllSchemas.get_schema_content_from_repo(
            project_id, schema_name
        )

        assert isinstance(result, JSONResponse)
        assert result.status_code == 404
        content = result.body.decode()
        assert f"Schema {schema_name} not found in project {project_id}" in content

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_schema_content_server_error(self):
        project_id = "test-project"
        schema_name = "error_schema"

        repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/schemas/{schema_name}.py"

        responses.add(
            responses.GET,
            repo_api_url,
            json={"message": "Internal Server Error"},
            status=500,
        )

        result = await GetAllSchemas.get_schema_content_from_repo(
            project_id, schema_name
        )

        assert isinstance(result, JSONResponse)
        assert result.status_code == 500
        content = result.body.decode()
        assert "Failed to fetch schema content" in content
