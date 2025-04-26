import base64
import json

import pytest
import responses
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.api.v1.routes.project_migrations import list_versions
from app.api.v1.services.project_migrations import GetAlembicVersions
from config import settings
from main import app

# Create test client
client = TestClient(app)


class TestGetVersionContent:

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_version_content_success(self):
        project_id = "test-project"
        version_name = "initial"

        # Mock the get_all_versions_from_repo response
        repo_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/alembic/versions"

        versions_data = [
            {
                "name": "0001_initial.py",
                "path": "alembic/versions/0001_initial.py",
                "type": "file",
                "url": f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/alembic/versions/0001_initial.py",
                "html_url": f"https://example.com/{project_id}/alembic/versions/0001_initial.py",
                "size": 1000,
            }
        ]

        responses.add(responses.GET, repo_url, json=versions_data, status=200)

        # Mock the version file content
        version_content = """
        \"\"\"initial migration

        Revision ID: abc123def456
        Revises:
        Create Date: 2023-10-25 10:00:00.000000

        \"\"\"
        revision = 'abc123def456'
        down_revision = None
        create_date = '2023-10-25 10:00:00.000000'

        def upgrade():
            pass

        def downgrade():
            pass
        """

        encoded_content = base64.b64encode(version_content.encode()).decode()

        # Mock response for the version content API call
        file_response_data = {
            "name": "0001_initial.py",
            "path": "alembic/versions/0001_initial.py",
            "content": encoded_content,
            "encoding": "base64",
            "url": versions_data[0]["url"],
            "html_url": versions_data[0]["html_url"],
            "size": len(version_content),
        }

        # Mock the version file content response for both the list call and the specific file call
        responses.add(
            responses.GET,
            versions_data[0]["url"],
            json={
                "content": encoded_content,
                "encoding": "base64",
                "name": "0001_initial.py",
                "path": "alembic/versions/0001_initial.py",
            },
            status=200,
        )

        # Second response is for when we get the specific file content
        responses.add(
            responses.GET,
            f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/alembic/versions/0001_initial.py",
            json=file_response_data,
            status=200,
        )

        result = await GetAlembicVersions.get_version_content_from_repo(
            project_id, version_name
        )

        assert isinstance(result, dict)
        assert result["name"] == version_name
        assert result["id"] == "0001"
        assert result["revision"] == "abc123def456"
        assert result["format"] == "text"
        assert "def upgrade():" in result["content"]
        assert result["content_base64"] == encoded_content
        assert "2023-10-25" in result["timestamp"]

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_version_content_version_not_found(self):
        project_id = "test-project"
        version_name = "nonexistent_version"

        # Mock the get_all_versions_from_repo response
        repo_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/alembic/versions"

        versions_data = [
            {
                "name": "0001_initial.py",
                "path": "alembic/versions/0001_initial.py",
                "type": "file",
                "url": f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/alembic/versions/0001_initial.py",
                "html_url": f"https://example.com/{project_id}/alembic/versions/0001_initial.py",
                "size": 1000,
            }
        ]

        responses.add(responses.GET, repo_url, json=versions_data, status=200)

        # Mock the version file content for the version that does exist (needed for the list call)
        version_content = """
        \"\"\"initial migration

        Revision ID: abc123def456
        Revises:
        Create Date: 2023-10-25 10:00:00.000000

        \"\"\"
        revision = 'abc123def456'
        down_revision = None
        create_date = '2023-10-25 10:00:00.000000'

        def upgrade():
            pass

        def downgrade():
            pass
        """

        encoded_content = base64.b64encode(version_content.encode()).decode()

        # Mock response for the existing version file content
        responses.add(
            responses.GET,
            versions_data[0]["url"],
            json={
                "content": encoded_content,
                "encoding": "base64",
                "name": "0001_initial.py",
                "path": "alembic/versions/0001_initial.py",
            },
            status=200,
        )

        result = await GetAlembicVersions.get_version_content_from_repo(
            project_id, version_name
        )

        assert isinstance(result, JSONResponse)
        assert result.status_code == 404

        content = result.body.decode()
        assert "Version not found" in content
        assert version_name in content

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_version_content_file_error(self):
        project_id = "test-project"
        version_name = "initial"

        # Mock the get_all_versions_from_repo response
        repo_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/alembic/versions"

        versions_data = [
            {
                "name": "0001_initial.py",
                "path": "alembic/versions/0001_initial.py",
                "type": "file",
                "url": f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/alembic/versions/0001_initial.py",
                "html_url": f"https://example.com/{project_id}/alembic/versions/0001_initial.py",
                "size": 1000,
            }
        ]

        responses.add(responses.GET, repo_url, json=versions_data, status=200)

        # Mock the version file content for the list call
        version_content = """
        \"\"\"initial migration

        Revision ID: abc123def456
        Revises:
        Create Date: 2023-10-25 10:00:00.000000

        \"\"\"
        revision = 'abc123def456'
        down_revision = None
        create_date = '2023-10-25 10:00:00.000000'

        def upgrade():
            pass

        def downgrade():
            pass
        """

        encoded_content = base64.b64encode(version_content.encode()).decode()

        # Mock response for the existing version file content (for the list call)
        responses.add(
            responses.GET,
            versions_data[0]["url"],
            json={
                "content": encoded_content,
                "encoding": "base64",
                "name": "0001_initial.py",
                "path": "alembic/versions/0001_initial.py",
            },
            status=200,
        )

        # Mock an error when trying to get the specific file content
        responses.add(
            responses.GET,
            f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/alembic/versions/0001_initial.py",
            json={"message": "Internal Server Error"},
            status=500,
        )

        result = await GetAlembicVersions.get_version_content_from_repo(
            project_id, version_name
        )

        assert isinstance(result, JSONResponse)
        assert result.status_code == 500

        content = result.body.decode()
        assert "Failed to fetch version content" in content


class TestVersionRoutes:

    @pytest.mark.asyncio
    async def test_list_versions_success(self, mock_get_all_versions):
        # Set up mock return value
        versions = [
            {
                "id": "0001",
                "name": "initial",
                "filename": "0001_initial.py",
                "path": "alembic/versions/0001_initial.py",
                "url": "https://example.com/0001_initial.py",
                "size": 1000,
                "revision": "abc123def456",
                "timestamp": "2023-10-25T10:00:00.000000",
            },
            {
                "id": "0002",
                "name": "create_user_table",
                "filename": "0002_create_user_table.py",
                "path": "alembic/versions/0002_create_user_table.py",
                "url": "https://example.com/0002_create_user_table.py",
                "size": 2000,
                "revision": "def456ghi789",
                "timestamp": "2023-10-26T11:00:00.000000",
            },
        ]
        mock_get_all_versions.return_value = versions

        response = await list_versions("test-project")

        assert isinstance(response, JSONResponse)
        assert response.status_code == 200

        content = json.loads(response.body.decode())
        assert content["message"] == "Alembic Versions Retrieved Successfully"
        assert len(content["data"]) == 2
        assert content["data"][0]["id"] == "0001"
        assert content["data"][0]["name"] == "initial"
        assert content["data"][1]["id"] == "0002"
        assert content["data"][1]["name"] == "create_user_table"

    @pytest.mark.asyncio
    async def test_list_versions_value_error(self, mock_get_all_versions):
        mock_get_all_versions.side_effect = ValueError("Alembic versions not found")

        response = await list_versions("nonexistent-project")

        assert isinstance(response, JSONResponse)
        assert response.status_code == 404

        content = json.loads(response.body.decode())
        assert content["message"] == "Alembic versions not found"
        assert "Alembic versions not found" in content["detail"]

    @pytest.mark.asyncio
    async def test_list_versions_exception(self, mock_get_all_versions):
        mock_get_all_versions.side_effect = Exception("Unexpected error")

        response = await list_versions("error-project")

        assert isinstance(response, JSONResponse)
        assert response.status_code == 500

        content = json.loads(response.body.decode())
        assert content["message"] == "Error retrieving alembic versions"
        assert "Unexpected error" in content["detail"]
