import importlib.util
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime

from fastapi import HTTPException, status

from app.api.v1.models.http_methods_test_endpoint import (
    TestRequestPayload,
    TestResponsePayload,
)

logger = logging.getLogger(__name__)


class TestEndpointService:
    """
    Service class responsible for handling the test execution logic for project endpoints.
    """

    def __init__(self):
        # Directory where projects are stored
        self.projects_dir = os.getenv(
            "PROJECTS_DIR", os.path.join(os.getcwd(), "repos")
        )
        # Cache to keep track of already installed projects
        self.installed_projects = set()

    async def execute_test(
        self, project_id: str, path: str, payload: TestRequestPayload, request_id: str
    ) -> TestResponsePayload:
        """
        Execute a test request against a project endpoint

        Args:
            project_id: The ID of the project containing the endpoint to test
            path: The endpoint path extracted from the URL
            payload: The TestRequestPayload containing request details
            request_id: A unique identifier for this test request

        Returns:
            TestResponsePayload: A structured response containing details of the test execution
        """
        # Find the project directory
        project_path = os.path.join(self.projects_dir, project_id)
        if not os.path.exists(project_path):
            logger.error(f"Project directory not found: {project_path}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{project_id}' not found",
            )

        # Set up test client for the project
        logger.info("Setting up test client for the project")
        main_file_path = os.path.join(project_path, "main.py")
        if not os.path.exists(main_file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"main.py not found in project '{project_id}'",
            )

        # Install requirements if needed
        await self._install_requirements(project_path, project_id)

        # Save the current sys.path and working directory
        original_path = sys.path.copy()
        original_cwd = os.getcwd()

        try:
            # Add the project directory to sys.path and change working directory
            sys.path.insert(0, project_path)
            os.chdir(project_path)

            # Import the main module
            main_module = await self._import_main_module(main_file_path)

            # Get the FastAPI app instance
            app = getattr(main_module, "app", None)
            if app is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Could not find FastAPI app instance in project",
                )

            # Create a test client
            from fastapi.testclient import TestClient

            client = TestClient(app)
            logger.info("Created test client for project FastAPI app")

            # Execute the test request
            return await self._execute_request(client, path, payload, request_id)

        finally:
            # Restore the original sys.path and working directory
            sys.path = original_path
            os.chdir(original_cwd)

    async def _install_requirements(self, project_path: str, project_id: str) -> None:
        """
        Install project requirements if they exist and haven't been installed yet

        Args:
            project_path: The path to the project directory
            project_id: The ID of the project
        """
        requirements_path = os.path.join(project_path, "requirements.txt")
        if (
            os.path.exists(requirements_path)
            and project_id not in self.installed_projects
        ):
            try:
                # Install requirements
                logger.info(f"Installing dependencies from {requirements_path}")
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", requirements_path],
                    check=True,
                    capture_output=True,
                )
                self.installed_projects.add(project_id)
                logger.info("Dependencies installed successfully")
            except subprocess.CalledProcessError as e:
                logger.warning(
                    f"Error installing dependencies: {e.stderr.decode() if e.stderr else 'Unknown error'}"
                )

    async def _import_main_module(self, main_file_path: str):
        """
        Import the main module of the project, handling any missing dependencies

        Args:
            main_file_path: Path to the main.py file

        Returns:
            The imported main module
        """
        # List of common local module names that should not be pip-installed
        LOCAL_MODULE_PREFIXES = [
            "schemas",
            "models",
            "helpers",
            "core",
            "utils",
            "config",
            "db",
        ]

        try:
            spec = importlib.util.spec_from_file_location("main", main_file_path)
            main_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(main_module)
            return main_module
        except ModuleNotFoundError as e:
            # Extract the missing module name
            missing_module = str(e).split("'")[1]

            # Check if this is likely a local module by examining the top-level package name
            top_level_package = (
                missing_module.split(".")[0]
                if "." in missing_module
                else missing_module
            )

            if top_level_package in LOCAL_MODULE_PREFIXES:
                # This is a local module, just log and continue without attempting to install
                logger.info(
                    f"Missing local module: {missing_module}, skipping installation"
                )
                # Re-raise the exception to be handled by the caller
                raise
            else:
                # For non-local modules, attempt to install with pip
                logger.info(
                    f"Missing external module: {missing_module}, attempting to install"
                )
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", missing_module],
                    check=True,
                    capture_output=True,
                )
                # Try loading the module again
                spec = importlib.util.spec_from_file_location("main", main_file_path)
                main_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(main_module)
                return main_module

    async def _execute_request(
        self, client, path: str, payload: TestRequestPayload, request_id: str
    ) -> TestResponsePayload:
        """
        Execute the actual HTTP request using the test client

        Args:
            client: The TestClient instance
            path: The endpoint path
            payload: The TestRequestPayload containing request details
            request_id: A unique identifier for this test request

        Returns:
            TestResponsePayload: A structured response containing details of the test execution
        """
        # Create request headers
        headers = payload.headers or {}
        if payload.contentType and "content-type" not in {
            k.lower(): v for k, v in headers.items()
        }:
            headers["Content-Type"] = payload.contentType

        # Build URL with query parameters if any
        url = f"/{path}"
        params = payload.queryParams or {}

        # Prepare request based on method
        method = payload.httpMethod.lower()
        logger.info(f"Executing {payload.httpMethod} request to {url}")

        start_time = time.time()

        # Execute the appropriate HTTP method
        response = await self._execute_http_method(
            client, method, url, headers, params, payload
        )

        end_time = time.time()
        logger.info(f"Response received in {end_time - start_time:.4f} seconds")
        logger.info(f"Response status code: {response.status_code}")

        # Process the response
        try:
            response_body = response.json()
            logger.info("Response parsed as JSON")
        except json.JSONDecodeError:
            response_body = response.text
            logger.info("Response parsed as text")

        response_size = len(response.content)
        logger.info(f"Response size: {response_size} bytes")

        # Create the response payload
        return TestResponsePayload(
            request_id=request_id,
            success=response.status_code < 400,
            statusCode=response.status_code,
            responseBody=response_body,
            responseHeaders=dict(response.headers),
            timeTaken=end_time - start_time,
            size=response_size,
            contentType=response.headers.get("content-type"),
            cookies=dict(response.cookies),
            redirects=None,  # TestClient doesn't track redirects the same way
            timestamp=datetime.utcnow(),
        )

    async def _execute_http_method(
        self,
        client,
        method: str,
        url: str,
        headers: dict,
        params: dict,
        payload: TestRequestPayload,
    ):
        """
        Execute the specific HTTP method requested

        Args:
            client: The TestClient instance
            method: The HTTP method to execute (lowercase)
            url: The endpoint URL
            headers: Request headers
            params: Query parameters
            payload: The TestRequestPayload containing request details

        Returns:
            The response from the test client
        """
        if method == "get":
            return client.get(url, headers=headers, params=params)
        elif method == "post":
            return await self._handle_request_with_body(
                client.post, url, headers, params, payload
            )
        elif method == "put":
            return await self._handle_request_with_body(
                client.put, url, headers, params, payload
            )
        elif method == "delete":
            return client.delete(url, headers=headers, params=params)
        elif method == "patch":
            return await self._handle_request_with_body(
                client.patch, url, headers, params, payload
            )
        elif method == "head":
            return client.head(url, headers=headers, params=params)
        elif method == "options":
            return client.options(url, headers=headers, params=params)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported HTTP method: {payload.httpMethod}",
            )

    async def _handle_request_with_body(
        self,
        method_func,
        url: str,
        headers: dict,
        params: dict,
        payload: TestRequestPayload,
    ):
        """
        Handle HTTP methods that can include a request body

        Args:
            method_func: The TestClient method function to use
            url: The endpoint URL
            headers: Request headers
            params: Query parameters
            payload: The TestRequestPayload containing request details

        Returns:
            The response from the test client
        """
        if payload.contentType == "application/json" and payload.requestBody:
            if isinstance(payload.requestBody, str):
                try:
                    json_data = json.loads(payload.requestBody)
                except json.JSONDecodeError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid JSON string in requestBody",
                    )
            else:
                json_data = payload.requestBody
            return method_func(url, headers=headers, params=params, json=json_data)
        else:
            data = (
                payload.requestBody
                if not isinstance(payload.requestBody, dict)
                else json.dumps(payload.requestBody)
            )
            return method_func(url, headers=headers, params=params, data=data)
