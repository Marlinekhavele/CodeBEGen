import app
import unittest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1.services.projects import ProjectInitService


# Test the download_project_gitea_repo method
class TestDownloadProjectGiteaRepo(unittest.TestCase):

    def setUp(self):
        # Set up temporary directories for testing
        self.temp_dir = tempfile.mkdtemp()
        self.test_output_path = Path(self.temp_dir) / "test_output"
        self.test_project_name = "test-project"

        # Create mock settings
        self.settings_patcher = patch('app.api.v1.services.projects.settings', autospec=True)
        self.mock_settings = self.settings_patcher.start()
        self.mock_settings.GITEA_API_URL = "https://git.example.com/api/v1"
        self.mock_settings.GIT_OWNER = "test-owner"
        self.mock_settings.GITEA_TOKEN = "test-token"

        # Mock httpx.AsyncClient
        self.httpx_patcher = patch('httpx.AsyncClient', autospec=True)
        self.mock_httpx = self.httpx_patcher.start()

        # Mock response
        self.mock_response = MagicMock()
        self.mock_response.status_code = 200
        self.mock_response.content = b"mock zip content"

        # Set up mock async client
        self.mock_client = AsyncMock()
        self.mock_client.__aenter__.return_value = self.mock_client
        self.mock_client.get.return_value = self.mock_response
        self.mock_httpx.return_value = self.mock_client

        # Mock other functions
        self.ensure_repos_dir_patcher = patch('app.api.v1.services.projects.ensure_repos_directory',
                                              autospec=True)
        self.mock_ensure_repos = self.ensure_repos_dir_patcher.start()

        self.get_default_dir_patcher = patch('app.api.v1.services.projects.get_default_download_directory',
                                             autospec=True)
        self.mock_get_default_dir = self.get_default_dir_patcher.start()
        self.mock_get_default_dir.return_value = Path(self.temp_dir) / "downloads"

        # Create mock REPOS_DIR
        self.repos_dir_patcher = patch('app.api.v1.services.projects.REPOS_DIR', Path(self.temp_dir) / "repos")
        self.mock_repos_dir = self.repos_dir_patcher.start()

        # Mock zipfile
        self.zipfile_patcher = patch('zipfile.ZipFile', autospec=True)
        self.mock_zipfile = self.zipfile_patcher.start()
        self.mock_zip_instance = MagicMock()
        self.mock_zipfile.return_value = self.mock_zip_instance
        self.mock_zip_instance.__enter__.return_value = self.mock_zip_instance
        self.mock_zip_instance.namelist.return_value = [f"{self.test_project_name}-main/file1.txt"]

    def tearDown(self):
        # Clean up temporary directories
        shutil.rmtree(self.temp_dir)

        # Stop patches
        self.settings_patcher.stop()
        self.httpx_patcher.stop()
        self.ensure_repos_dir_patcher.stop()
        self.get_default_dir_patcher.stop()
        self.repos_dir_patcher.stop()
        self.zipfile_patcher.stop()

    @pytest.mark.asyncio
    async def test_download_with_output_path_as_zip(self):
        """Test downloading to a specific output path as zip"""
        # Create directory for the test output path
        os.makedirs(self.test_output_path.parent, exist_ok=True)

        # Run the test
        result = await ProjectInitService.download_project_gitea_repo(
            self.test_project_name,
            self.test_output_path,
            save_as_zip=True
        )

        # Verify the correct URL was used
        expected_url = f"{self.mock_settings.GITEA_API_URL}/repos/{self.mock_settings.GIT_OWNER}/{self.test_project_name}/archive/main.zip"
        self.mock_client.get.assert_called_once_with(
            expected_url,
            headers={"Authorization": f"token {self.mock_settings.GITEA_TOKEN}"}
        )

        # Verify the file was saved to the correct location
        expected_path = self.test_output_path
        if expected_path.suffix != '.zip':
            expected_path = expected_path.parent / f"{self.test_project_name}.zip"
        self.assertEqual(result, expected_path)

    @pytest.mark.asyncio
    async def test_download_to_downloads_folder(self):
        """Test downloading to the downloads folder"""
        # Run the test
        result = await ProjectInitService.download_project_gitea_repo(
            self.test_project_name,
            use_default_download_dir=True,
            save_as_zip=True
        )

        # Verify the file was saved to the downloads folder
        expected_path = self.mock_get_default_dir.return_value / f"{self.test_project_name}.zip"
        self.assertEqual(result, expected_path)

        # Verify get_default_download_directory was called
        self.mock_get_default_dir.assert_called_once()

        # Ensure ensure_repos_directory was not called
        self.mock_ensure_repos.assert_not_called()

    @pytest.mark.asyncio
    async def test_download_to_repos_folder(self):
        """Test downloading to the default repos folder"""
        # Run the test
        result = await ProjectInitService.download_project_gitea_repo(
            self.test_project_name,
            use_default_download_dir=False,
            save_as_zip=True
        )

        # Verify the file was saved to the repos folder
        expected_path = self.mock_repos_dir / f"{self.test_project_name}.zip"
        self.assertEqual(result, expected_path)

        # Verify ensure_repos_directory was called
        self.mock_ensure_repos.assert_called_once()

        # Ensure get_default_download_directory was not called
        self.mock_get_default_dir.assert_not_called()

    @pytest.mark.asyncio
    async def test_download_and_extract(self):
        """Test downloading and extracting the zip"""
        # Run the test
        result = await ProjectInitService.download_project_gitea_repo(
            self.test_project_name,
            save_as_zip=False
        )

        # Verify zipfile was used to extract
        self.mock_zipfile.assert_called()
        self.mock_zip_instance.extractall.assert_called_once()

        # Verify the correct destination
        expected_path = self.mock_repos_dir / self.test_project_name
        self.assertEqual(result, expected_path)

    @pytest.mark.asyncio
    async def test_http_error_handling(self):
        """Test handling of HTTP errors"""
        # Set up mock response with error
        self.mock_response.status_code = 404
        self.mock_response.text = "Not Found"

        # Verify exception is raised
        with self.assertRaises(HTTPException) as context:
            await ProjectInitService.download_project_gitea_repo(self.test_project_name)

        # Check the exception details
        self.assertEqual(context.exception.status_code, 404)
        self.assertIn("Failed to download repository", context.exception.detail)

    @pytest.mark.asyncio
    async def test_network_error_handling(self):
        """Test handling of network errors"""
        # Make the client.get raise an exception
        request_error = httpx.RequestError("Connection error", request=None)
        self.mock_client.get.side_effect = request_error

        # Verify exception is raised
        with self.assertRaises(HTTPException) as context:
            await ProjectInitService.download_project_gitea_repo(self.test_project_name)

        # Check the exception details
        self.assertEqual(context.exception.status_code, 500)
        self.assertIn("Error during request to Gitea", context.exception.detail)


# Test the download_repository_file endpoint
class TestDownloadRepositoryFileEndpoint(unittest.TestCase):

    def setUp(self):
        # Set up TestClient
        self.client = TestClient(app)

        # Create temporary file for testing
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file_path = Path(self.temp_dir) / "test.zip"

        # Mock the download_project_gitea_repo method
        self.download_patcher = patch.object(
            ProjectInitService, 'download_project_gitea_repo', autospec=True
        )
        self.mock_download = self.download_patcher.start()
        self.mock_download.return_value = self.temp_file_path

        # Mock FileResponse
        self.file_response_patcher = patch('fastapi.responses.FileResponse', autospec=True)
        self.mock_file_response = self.file_response_patcher.start()
        self.mock_response = MagicMock()
        self.mock_file_response.return_value = self.mock_response

        # Mock tempfile.NamedTemporaryFile
        self.named_temp_file_patcher = patch('tempfile.NamedTemporaryFile', autospec=True)
        self.mock_named_temp_file = self.named_temp_file_patcher.start()
        self.mock_temp_file = MagicMock()
        self.mock_temp_file.name = str(self.temp_file_path)
        self.mock_named_temp_file.return_value = self.mock_temp_file

        # Create the file for testing
        with open(self.temp_file_path, 'wb') as f:
            f.write(b"test content")

    def tearDown(self):
        # Clean up
        shutil.rmtree(self.temp_dir)

        # Stop patches
        self.download_patcher.stop()
        self.file_response_patcher.stop()
        self.named_temp_file_patcher.stop()

    @pytest.mark.asyncio
    async def test_download_repository_file_success(self):
        """Test successful download of repository file"""
        # Set up test data
        project_name = "test-project"

        # Verify download_project_gitea_repo was called correctly
        self.mock_download.assert_called_once()
        args, kwargs = self.mock_download.call_args
        self.assertEqual(args[0], project_name)  # First argument should be project_name
        self.assertEqual(kwargs.get('save_as_zip', True), True)  # save_as_zip should be True

        # Verify FileResponse was created correctly
        self.mock_file_response.assert_called_once()
        args, kwargs = self.mock_file_response.call_args
        self.assertEqual(kwargs['path'], self.temp_file_path)
        self.assertEqual(kwargs['filename'], f"{project_name}.zip")
        self.assertEqual(kwargs['media_type'], "application/zip")

        # Verify background task was set
        self.assertTrue(hasattr(self.mock_response, 'background'))

    @pytest.mark.asyncio
    async def test_download_with_custom_filename(self):
        """Test download with custom filename"""
        custom_filename = "custom-name.zip"

        # Verify FileResponse used the custom filename
        self.mock_file_response.assert_called_once()
        args, kwargs = self.mock_file_response.call_args
        self.assertEqual(kwargs['filename'], custom_filename)

    @pytest.mark.asyncio
    async def test_download_error_handling(self):
        """Test error handling in download endpoint"""
        # Make the download method raise an exception
        self.mock_download.side_effect = Exception("Test error")

        # Test making the request
        with self.assertRaises(Exception):
            await app.routes[-1].endpoint("test-project")