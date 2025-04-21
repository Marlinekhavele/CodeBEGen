import base64

import pytest
import responses
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.api.v1.services.project_helpers import GetAllHelpers
from config import settings
from main import app

client = TestClient(app)


class TestGetHelperContent:

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_helper_content_success_python(self):
        project_id = "test-project"
        helper_name = "test_helper"
        helper_file = "test_helper.py"

        helper_content = "def test_function():\n    return 'Hello, world!'"

        encoded_content = base64.b64encode(helper_content.encode()).decode()

        repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/helpers/{helper_file}"

        response_data = {
            "name": helper_file,
            "path": f"helpers/{helper_file}",
            "content": encoded_content,
            "encoding": "base64",
            "url": repo_api_url,
            "html_url": f"https://example.com/{project_id}/helpers/{helper_file}",
            "size": len(helper_content),
        }

        responses.add(responses.GET, repo_api_url, json=response_data, status=200)

        result = await GetAllHelpers.get_helper_content_from_repo(
            project_id, helper_name
        )

        assert isinstance(result, dict)
        assert result["name"] == helper_name
        assert result["format"] == "text"
        assert result["content"] == helper_content
        assert result["content_base64"] == encoded_content
        assert result["type"] == "python"

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_helper_content_success_shell(self):
        project_id = "test-project"
        helper_name = "deploy_helper"
        helper_file = "deploy_helper.sh"

        helper_content = "#!/bin/bash\necho 'Deploying...'"

        encoded_content = base64.b64encode(helper_content.encode()).decode()

        repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/helpers/{helper_file}"

        response_data = {
            "name": helper_file,
            "path": f"helpers/{helper_file}",
            "content": encoded_content,
            "encoding": "base64",
            "url": repo_api_url,
            "html_url": f"https://example.com/{project_id}/helpers/{helper_file}",
            "size": len(helper_content),
        }

        responses.add(responses.GET, repo_api_url, json=response_data, status=200)

        result = await GetAllHelpers.get_helper_content_from_repo(
            project_id, helper_name
        )

        assert isinstance(result, dict)
        assert result["name"] == helper_name
        assert result["format"] == "text"
        assert result["content"] == helper_content
        assert result["content_base64"] == encoded_content
        assert result["type"] == "shell"

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_helper_content_with_extension(self):
        project_id = "test-project"
        helper_name = "test_helper.py"
        expected_helper_name = "test_helper"

        helper_content = "def another_test():\n    pass"
        encoded_content = base64.b64encode(helper_content.encode()).decode()

        repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/helpers/{helper_name}"

        response_data = {
            "name": helper_name,
            "path": f"helpers/{helper_name}",
            "content": encoded_content,
            "encoding": "base64",
            "url": repo_api_url,
            "html_url": f"https://example.com/{project_id}/helpers/{helper_name}",
            "size": len(helper_content),
        }

        responses.add(responses.GET, repo_api_url, json=response_data, status=200)

        result = await GetAllHelpers.get_helper_content_from_repo(
            project_id, helper_name
        )

        assert result["name"] == expected_helper_name
        assert result["content"] == helper_content
        assert result["type"] == "python"

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_helper_content_404(self):
        # Test when helper doesn't exist
        project_id = "test-project"
        helper_name = "nonexistent_helper"

        py_repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/helpers/{helper_name}.py"
        sh_repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/helpers/{helper_name}.sh"

        responses.add(
            responses.GET, py_repo_api_url, json={"message": "Not Found"}, status=404
        )
        responses.add(
            responses.GET, sh_repo_api_url, json={"message": "Not Found"}, status=404
        )

        result = await GetAllHelpers.get_helper_content_from_repo(
            project_id, helper_name
        )

        assert isinstance(result, JSONResponse)
        assert result.status_code == 404
        content = result.body.decode()
        assert f"Helper {helper_name} not found in project {project_id}" in content

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_helper_content_server_error(self):
        project_id = "test-project"
        helper_name = "error_helper"

        repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/helpers/{helper_name}.py"

        responses.add(
            responses.GET,
            repo_api_url,
            json={"message": "Internal Server Error"},
            status=500,
        )

        result = await GetAllHelpers.get_helper_content_from_repo(
            project_id, helper_name
        )

        assert isinstance(result, JSONResponse)
        assert result.status_code == 500
        content = result.body.decode()
        assert "Failed to fetch helper content" in content
