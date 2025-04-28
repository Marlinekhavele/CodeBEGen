from fastapi import APIRouter, HTTPException, status, Request
import uuid, logging


from app.api.v1.models.http_methods_test_endpoint import (
    TestRequestPayload,
    TestResponsePayload,
)
from app.api.v1.services.http_methods_test_endpoint_service import TestEndpointService
from app.api.v1.utils.error_response import error_response
from app.api.v1.utils.success_response import success_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["test-endpoint"])


@router.post("/test-endpoint/project/{project_id}", response_model=TestResponsePayload)
async def test_project_endpoint(project_id: str, payload: TestRequestPayload):
    """
    Test an endpoint within a generated project by dynamically importing and executing it.

    Args:
        project_id: The ID of the project containing the endpoint to test
        payload: The TestRequestPayload containing request details

    Returns:
        TestResponsePayload: A structured response containing details of the response
    """
    request_id = str(uuid.uuid4())
    logger.info(f"Received test request for project: {project_id}")
    logger.info(f"Original endpoint URL: {payload.endpointUrl}")
    logger.info(f"HTTP Method: {payload.httpMethod}")

    # Extract the endpoint path from the payload URL
    url = str(payload.endpointUrl)

    # Handle different URL formats
    if url.startswith('/'):
        # Simple path like "/health"
        path = url.lstrip('/')
    elif url.startswith(f'http://{project_id}/'):
        # Project-specific URL like "http://{project_id}/{path}"
        path = url.split('/', 3)[-1] if len(url.split('/', 3)) > 3 else ""
    else:
        # Assume it's just the path without leading slash
        path = url

    logger.info(f"Endpoint path: {path}")

    try:
        # Initialize the service to handle the testing logic
        test_service = TestEndpointService()

        # Execute the test using the service
        response_data = await test_service.execute_test(
            project_id=project_id,
            path=path,
            payload=payload,
            request_id=request_id
        )

        logger.info(f"Request completed successfully: {response_data.statusCode}")
        return success_response(
            status_code=status.HTTP_200_OK,
            data=response_data,
            message="Request completed successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error while testing project: {str(e)}", exc_info=True)
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error while testing project",
            detail=str(e)
        )