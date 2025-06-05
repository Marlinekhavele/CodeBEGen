import importlib.util
import json
import logging
import os
import re
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
            response = await self._execute_request(client, path, payload, request_id)
            # Check if this was a database-modifying operation and commit changes if successful
            if self._is_database_modifying_request(
                payload.httpMethod, response.statusCode
            ):
                # Note: We need to call this from the original working directory
                original_cwd_for_git = original_cwd
                await self._commit_database_changes_to_gitea(
                    project_id,
                    project_path,
                    payload.httpMethod,
                    path,
                    original_cwd_for_git,
                )

            return response

        finally:
            # Restore the original sys.path and working directory
            sys.path = original_path
            os.chdir(original_cwd)

    def _is_database_modifying_request(
        self, http_method: str, status_code: int
    ) -> bool:
        """
        Determine if this request likely modified the database

        Args:
            http_method: The HTTP method used
            status_code: The response status code

        Returns:
            bool: True if this request likely modified the database
        """  # Check if this is a database-modifying HTTP method and the request was successful
        modifying_methods = ["POST", "PUT", "PATCH", "DELETE"]
        successful_status_codes = [200, 201, 202, 204]

        return (
            http_method.upper() in modifying_methods
            and status_code in successful_status_codes
        )

    async def _commit_database_changes_to_gitea(
        self,
        project_id: str,
        project_path: str,
        http_method: str,
        endpoint_path: str,
        original_cwd: str,
    ) -> None:
        """
        Commit database changes back to the Gitea repository

        Args:
            project_id: The project identifier
            project_path: Path to the local project directory
            http_method: The HTTP method that was executed
            endpoint_path: The endpoint path that was tested
            original_cwd: The original working directory to restore context for GitService
        """
        # Save current working directory
        current_cwd = os.getcwd()

        try:
            # Change back to original working directory for GitService operations
            os.chdir(original_cwd)

            # Check if there are database files in the project
            db_dir = os.path.join(project_path, "storage", "db")
            if not os.path.exists(db_dir):
                logger.info(f"No database directory found in project {project_id}")
                return

            # Find SQLite database files
            db_files = []
            for file in os.listdir(db_dir):
                if file.endswith((".sqlite", ".sqlite3", ".db")):
                    db_files.append(os.path.join("storage", "db", file))

            if not db_files:
                logger.info(f"No database files found in project {project_id}")
                return

            logger.info(f"Found {len(db_files)} database files to commit: {db_files}")

            # Use GitService to commit the database files
            from app.api.v1.services.git_service import GitService

            commit_message = (
                f"Update database after {http_method} request to {endpoint_path}"
            )

            commit_hash = await GitService.commit_multiple_files_update(
                project_id=project_id,
                file_paths=db_files,
                commit_message=commit_message,
            )

            logger.info(
                f"Successfully committed database changes to Gitea. Commit hash: {commit_hash}"
            )

        except Exception as e:
            # Log the error but don't fail the test response
            logger.error(f"Failed to commit database changes to Gitea: {str(e)}")
            logger.error(
                "This does not affect the test execution, but database changes won't be synced to Gitea"
            )
        finally:
            # Always restore the current working directory
            os.chdir(current_cwd)

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

    async def execute_test_with_auto_fix(
        self,
        project_id: str,
        path: str,
        payload: TestRequestPayload,
        request_id: str,
        auto_fix: bool = True,
        max_retries: int = 2,
    ) -> TestResponsePayload:
        """
        Execute a test request with automatic error fixing and retry capability.

        Args:
            project_id: The ID of the project containing the endpoint to test
            path: The endpoint path extracted from the URL
            payload: The TestRequestPayload containing request details
            request_id: A unique identifier for this test request
            auto_fix: Whether to automatically fix errors and retry
            max_retries: Maximum number of retry attempts for auto-fixing

        Returns:
            TestResponsePayload: A structured response containing details of the test execution
        """
        retries = 0
        last_error = None

        while retries <= max_retries:
            try:
                # Try the normal test execution
                return await self.execute_test(project_id, path, payload, request_id)

            except Exception as e:
                # Get the error message and traceback
                error_msg = str(e)
                import traceback

                error_trace = (
                    traceback.format_exc()
                )  # Save for later if we can't fix it
                last_error = error_msg

                logger.error(f"Test failed (attempt {retries + 1}): {error_msg}")
                logger.debug(f"Error trace: {error_trace}")

                # Try to fix the code if auto_fix is enabled and we have retries left
                if auto_fix and retries < max_retries:
                    # Try to identify and fix the file with the error
                    fixed = await self._fix_code_from_error(
                        project_id, error_msg, error_trace, path
                    )

                    if fixed:
                        logger.info(
                            f"Fixed code error, retrying test (attempt {retries + 2})..."
                        )
                        retries += 1
                        continue
                    else:
                        logger.warning("Failed to fix code error, trying next retry")
                else:
                    logger.warning("Auto-fix disabled or max retries reached")

                retries += 1

        # If we get here, all retries failed
        logger.error(f"All retry attempts failed. Last error: {last_error}")

        # Create a response indicating the failure
        return TestResponsePayload(
            request_id=request_id,
            success=False,
            statusCode=500,
            responseBody={
                "detail": last_error or "Test failed after all retry attempts"
            },
            responseHeaders={},
            timeTaken=0.0,
            size=0,
            contentType=None,
            cookies={},
            redirects=None,
            timestamp=datetime.utcnow(),
        )

    async def _fix_code_from_error(
        self,
        project_id: str,
        error_message: str,
        traceback_text: str,
        endpoint_path: str,
    ) -> bool:
        """
        Automatically fix code based on error message and traceback.

        Args:
            project_id: The project ID
            error_message: The error message
            traceback_text: The full traceback
            endpoint_path: The endpoint path being tested

        Returns:
            bool: True if code was successfully fixed, False otherwise
        """
        try:
            # Identify the file that needs fixing
            file_to_fix = self._identify_file_from_error(
                traceback_text, project_id, endpoint_path
            )

            if not file_to_fix:
                logger.warning("Could not identify file to fix from error message")
                return False

            # Get the full path to the file
            project_path = os.path.join(self.projects_dir, project_id)
            full_path = os.path.join(project_path, file_to_fix)

            if not os.path.exists(full_path):
                logger.error(f"File to fix not found: {full_path}")
                return False

            # Read the current code
            with open(full_path, "r", encoding="utf-8") as f:
                current_code = f.read()

            # Determine language from file extension
            _, ext = os.path.splitext(file_to_fix)
            language = (
                "python"
                if ext == ".py"
                else "javascript" if ext in [".js", ".ts"] else "python"
            )

            # Use LangchainService to fix the code
            from app.api.v1.services.langchain_service import LangchainService

            logger.info(f"Attempting to fix {file_to_fix} for error: {error_message}")

            fixed_result = await LangchainService.fix_code_error(
                project_id=project_id,
                error_message=error_message,
                generated_code=current_code,
                language=language,
                file_path=file_to_fix,
                context=f"Testing endpoint: {endpoint_path}",
            )

            if not fixed_result or "generated_code" not in fixed_result:
                logger.error("Failed to get fixed code from LLM")
                return False

            fixed_code = fixed_result.get("generated_code")

            # Write the fixed code back to the file
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(fixed_code)

            logger.info(f"Successfully fixed code in {file_to_fix}")
            return True

        except Exception as e:
            logger.error(f"Error during code fixing: {str(e)}", exc_info=True)
            return False

    def _identify_file_from_error(
        self, traceback_text: str, project_id: str, endpoint_path: str
    ) -> str:
        """
        Analyze the traceback to identify the file that needs fixing.

        Args:
            traceback_text: The full traceback from the error
            project_id: The project ID
            endpoint_path: The endpoint path being tested

        Returns:
            str: Relative path to the file with the error or None if not found
        """
        try:
            project_path = os.path.join(self.projects_dir, project_id)

            # Look for file paths in the traceback that are within the project
            import re

            # Pattern to match file paths in traceback
            file_pattern = r'File [\'"]([^"\']+)[\'"]'
            matches = re.findall(file_pattern, traceback_text)

            # Filter matches to only include files within the project directory
            project_files = []
            for file_path in matches:
                if project_path in file_path:
                    # Convert to relative path
                    rel_path = os.path.relpath(file_path, project_path)
                    if not rel_path.startswith(".."):  # Ensure it's within project
                        project_files.append(rel_path)

            if project_files:
                # Return the most relevant file (usually the last one in the stack trace)
                return project_files[-1]

            # Fallback: Try to guess based on error type and endpoint path
            return self._guess_file_from_error_type(
                traceback_text, endpoint_path, project_path
            )

        except Exception as e:
            logger.error(f"Error identifying file from traceback: {str(e)}")
            return None

    def _guess_file_from_error_type(
        self, error_text: str, endpoint_path: str, project_path: str
    ) -> str:
        """
        Make an educated guess about which file has the error based on error patterns.

        Args:
            error_text: The error message and traceback
            endpoint_path: The endpoint path being tested
            project_path: The full path to the project directory

        Returns:
            str: Relative path to likely file with error, or None
        """
        # Pydantic configuration errors usually occur in schema files
        if "from_attributes" in error_text and "use from_orm" in error_text:
            # Look for schema files
            schema_patterns = [
                "schemas/*.py",
                f"schemas/{endpoint_path}.py",
                f"schemas/{endpoint_path}_schema.py",
            ]

            for pattern in schema_patterns:
                if "*" in pattern:
                    # Find all schema files
                    import glob

                    schema_files = glob.glob(os.path.join(project_path, pattern))
                    if schema_files:
                        return os.path.relpath(schema_files[0], project_path)
                else:
                    if os.path.exists(os.path.join(project_path, pattern)):
                        return pattern

        # Parameter mismatch errors usually occur in helper files
        if "got an unexpected keyword argument" in error_text:
            # Extract function name from error
            func_match = re.search(
                r"(\w+)\(\) got an unexpected keyword argument", error_text
            )
            if func_match:
                func_name = func_match.group(1)
                helper_patterns = [
                    f"helpers/{func_name}_helpers.py",
                    f"helpers/{endpoint_path}_helpers.py",
                    "helpers/helpers.py",
                ]

                for pattern in helper_patterns:
                    if os.path.exists(os.path.join(project_path, pattern)):
                        return pattern

        # Default: try endpoint file itself
        if endpoint_path:
            endpoint_patterns = [
                f"endpoints/{endpoint_path}.py",
                f"endpoints/{endpoint_path}.post.py",
                f"endpoints/{endpoint_path}.get.py",
                f"routes/{endpoint_path}.py",
            ]

            for pattern in endpoint_patterns:
                if os.path.exists(os.path.join(project_path, pattern)):
                    return pattern

        return None
