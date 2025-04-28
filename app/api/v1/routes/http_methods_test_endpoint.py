from fastapi import APIRouter, HTTPException, status, Request
import json, time, uuid, logging, os, sys, importlib.util, subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.api.v1.models.http_methods_test_endpoint import (
    AuthType,
    TestRequestPayload,
    TestResponsePayload,
)
from app.api.v1.utils.http_methods_test_endpoint_helpers import add_auth_to_request

# Configure logging
logger = logging.getLogger("project_endpoint_test")
logger.setLevel(logging.INFO)

router = APIRouter(tags=["test-endpoint"])

# Directory where projects are stored
PROJECTS_DIR = os.getenv("PROJECTS_DIR", os.path.join(os.getcwd(), "repos"))

# Cache to keep track of already installed projects
installed_projects = set()


@router.post("/test-endpoint/project/{project_id}", response_model=TestResponsePayload)
async def test_project_endpoint(project_id: str, payload: TestRequestPayload, request: Request):
    """
    Test an endpoint within a generated project by dynamically importing and executing it.

    Args:
        project_id: The ID of the project containing the endpoint to test
        payload: The TestRequestPayload containing details of the request to be sent

    Returns:
        TestResponsePayload: A structured response containing details of the response
    """
    request_id = str(uuid.uuid4())
    logger.info(f"Received test request for project: {project_id}")
    logger.info(f"Original endpoint URL: {payload.endpointUrl}")
    logger.info(f"HTTP Method: {payload.httpMethod}")

    # Find the project directory
    project_path = os.path.join(PROJECTS_DIR, project_id)
    if not os.path.exists(project_path):
        logger.error(f"Project directory not found: {project_path}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found"
        )

    # Extract the endpoint path from the payload URL
    path = str(payload.endpointUrl).split("/", 3)[-1] if "/" in str(payload.endpointUrl) else ""
    logger.info(f"Endpoint path: {path}")

    try:
        # Set up test client for the project
        logger.info("Setting up test client for the project")
        main_file_path = os.path.join(project_path, "main.py")
        if not os.path.exists(main_file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"main.py not found in project '{project_id}'"
            )

        # Install requirements if needed
        requirements_path = os.path.join(project_path, "requirements.txt")
        if os.path.exists(requirements_path) and project_id not in installed_projects:
            try:
                # Install requirements
                logger.info(f"Installing dependencies from {requirements_path}")
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", requirements_path],
                    check=True,
                    capture_output=True
                )
                installed_projects.add(project_id)
                logger.info("Dependencies installed successfully")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Error installing dependencies: {e.stderr.decode() if e.stderr else 'Unknown error'}")

        # Save the current sys.path and working directory
        original_path = sys.path.copy()
        original_cwd = os.getcwd()

        try:
            # Add the project directory to sys.path and change working directory
            sys.path.insert(0, project_path)
            os.chdir(project_path)

            # Import the main module
            try:
                spec = importlib.util.spec_from_file_location("main", main_file_path)
                main_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(main_module)
            except ModuleNotFoundError as e:
                # If a module is missing, we'll install it automatically
                missing_module = str(e).split("'")[1]
                logger.info(f"Missing module: {missing_module}, attempting to install")
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", missing_module],
                    check=True,
                    capture_output=True
                )
                # Try loading the module again
                spec = importlib.util.spec_from_file_location("main", main_file_path)
                main_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(main_module)

            # Get the FastAPI app instance
            app = getattr(main_module, "app", None)
            if app is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Could not find FastAPI app instance in project"
                )

            # Create a test client
            from fastapi.testclient import TestClient
            client = TestClient(app)
            logger.info("Created test client for project FastAPI app")

            # Execute the test request
            start_time = time.time()

            # Create request headers
            headers = payload.headers or {}
            if payload.contentType and "content-type" not in {k.lower(): v for k, v in headers.items()}:
                headers["Content-Type"] = payload.contentType

            # Build URL with query parameters if any
            url = f"/{path}"
            params = payload.queryParams or {}

            # Prepare request based on method
            method = payload.httpMethod.lower()
            logger.info(f"Executing {payload.httpMethod} request to {url}")

            # Handle different HTTP methods and their parameters properly
            if method == "get":
                response = client.get(url, headers=headers, params=params)
            elif method == "post":
                if payload.contentType == "application/json" and payload.requestBody:
                    if isinstance(payload.requestBody, str):
                        try:
                            json_data = json.loads(payload.requestBody)
                        except json.JSONDecodeError:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invalid JSON string in requestBody"
                            )
                    else:
                        json_data = payload.requestBody
                    response = client.post(url, headers=headers, params=params, json=json_data)
                else:
                    data = payload.requestBody if not isinstance(payload.requestBody, dict) else json.dumps(
                        payload.requestBody)
                    response = client.post(url, headers=headers, params=params, data=data)
            elif method == "put":
                if payload.contentType == "application/json" and payload.requestBody:
                    if isinstance(payload.requestBody, str):
                        try:
                            json_data = json.loads(payload.requestBody)
                        except json.JSONDecodeError:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invalid JSON string in requestBody"
                            )
                    else:
                        json_data = payload.requestBody
                    response = client.put(url, headers=headers, params=params, json=json_data)
                else:
                    data = payload.requestBody if not isinstance(payload.requestBody, dict) else json.dumps(
                        payload.requestBody)
                    response = client.put(url, headers=headers, params=params, data=data)
            elif method == "delete":
                response = client.delete(url, headers=headers, params=params)
            elif method == "patch":
                if payload.contentType == "application/json" and payload.requestBody:
                    if isinstance(payload.requestBody, str):
                        try:
                            json_data = json.loads(payload.requestBody)
                        except json.JSONDecodeError:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Invalid JSON string in requestBody"
                            )
                    else:
                        json_data = payload.requestBody
                    response = client.patch(url, headers=headers, params=params, json=json_data)
                else:
                    data = payload.requestBody if not isinstance(payload.requestBody, dict) else json.dumps(
                        payload.requestBody)
                    response = client.patch(url, headers=headers, params=params, data=data)
            elif method == "head":
                response = client.head(url, headers=headers, params=params)
            elif method == "options":
                response = client.options(url, headers=headers, params=params)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported HTTP method: {payload.httpMethod}"
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
            response_data = TestResponsePayload(
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

            logger.info(f"Request completed successfully: {response.status_code}")
            return response_data

        finally:
            # Restore the original sys.path and working directory
            sys.path = original_path
            os.chdir(original_cwd)

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error while testing project: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error testing project: {str(e)}"
        )