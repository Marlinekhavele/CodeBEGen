import base64

import pytest
import responses
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.api.v1.services.project_migrations import GetAlembicVersions
from config import settings
from main import app

# Create test client
client = TestClient(app)


class TestGetAllVersions:

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_all_versions_success(self):
        # Mocking the API response for the repository contents
        project_id = "test-project"
        repo_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/alembic/versions"

        versions_data = [
            {
                "name": "0001_initial.py",
                "path": "alembic/versions/0001_initial.py",
                "type": "file",
                "url": f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/alembic/versions/0001_initial.py",
                "html_url": f"https://example.com/{project_id}/alembic/versions/0001_initial.py",
                "size": 1000,
            },
            {
                "name": "0002_create_user_table.py",
                "path": "alembic/versions/0002_create_user_table.py",
                "type": "file",
                "url": f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/alembic/versions/0002_create_user_table.py",
                "html_url": f"https://example.com/{project_id}/alembic/versions/0002_create_user_table.py",
                "size": 2000,
            },
            {
                "name": "__pycache__",  # Should be filtered out
                "path": "alembic/versions/__pycache__",
                "type": "dir",
                "url": f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/alembic/versions/__pycache__",
                "html_url": f"https://example.com/{project_id}/alembic/versions/__pycache__",
                "size": 0,
            },
        ]

        responses.add(responses.GET, repo_url, json=versions_data, status=200)

        # Mock file content responses with appropriate revision and timestamp data
        initial_content = """
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

        user_table_content = """
        \"\"\"create user table

        Revision ID: def456ghi789
        Revises: abc123def456
        Create Date: 2023-10-26 11:00:00.000000

        \"\"\"
        revision = 'def456ghi789'
        down_revision = 'abc123def456'
        create_date = '2023-10-26 11:00:00.000000'

        def upgrade():
            pass

        def downgrade():
            pass
        """

        # Add mock responses for each file
        responses.add(
            responses.GET,
            versions_data[0]["url"],
            json={
                "content": base64.b64encode(initial_content.encode()).decode(),
                "encoding": "base64",
            },
            status=200,
        )

        responses.add(
            responses.GET,
            versions_data[1]["url"],
            json={
                "content": base64.b64encode(user_table_content.encode()).decode(),
                "encoding": "base64",
            },
            status=200,
        )

        result = await GetAlembicVersions.get_all_versions_from_repo(project_id)

        assert len(result) == 2
        assert result[0]["id"] == "0001"
        assert result[0]["name"] == "initial"
        assert result[0]["revision"] == "abc123def456"
        assert "2023-10-25" in result[0]["timestamp"]

        assert result[1]["id"] == "0002"
        assert result[1]["name"] == "create_user_table"
        assert result[1]["revision"] == "def456ghi789"
        assert "2023-10-26" in result[1]["timestamp"]

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_all_versions_404(self):
        # Test when versions directory doesn't exist
        project_id = "nonexistent-project"
        repo_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/alembic/versions"

        responses.add(
            responses.GET, repo_url, json={"message": "Not Found"}, status=404
        )

        result = await GetAlembicVersions.get_all_versions_from_repo(project_id)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 404

        content = result.body.decode()
        assert "Alembic versions directory not found" in content

    @pytest.mark.asyncio
    @responses.activate
    async def test_get_all_versions_server_error(self):
        project_id = "error-project"
        repo_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/alembic/versions"

        responses.add(
            responses.GET,
            repo_url,
            json={"message": "Internal Server Error"},
            status=500,
        )

        result = await GetAlembicVersions.get_all_versions_from_repo(project_id)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 500

        content = result.body.decode()
        assert "Failed to fetch alembic versions" in content
