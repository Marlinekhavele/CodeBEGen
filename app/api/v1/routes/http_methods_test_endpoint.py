import logging
import os
import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.v1.models.http_methods_test_endpoint import (
    CodeFixPayload,
    CodeFixResponse,
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
    if url.startswith("/"):
        # Simple path like "/health"
        path = url.lstrip("/")
    elif url.startswith(f"http://{project_id}/"):
        # Project-specific URL like "http://{project_id}/{path}"
        path = url.split("/", 3)[-1] if len(url.split("/", 3)) > 3 else ""
    else:
        # Assume it's just the path without leading slash
        path = url

    logger.info(f"Endpoint path: {path}")

    try:
        # Initialize the service to handle the testing logic
        test_service = TestEndpointService()

        # Execute the test using the service
        response_data = await test_service.execute_test(
            project_id=project_id, path=path, payload=payload, request_id=request_id
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

        # Get traceback for better error debugging
        import traceback

        error_trace = traceback.format_exc()

        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error while testing project",
            detail=str(e),
            # Include traceback in response for debugging - could be used by frontend
            # for automatic error fixing
            context={"traceback": error_trace, "project_id": project_id},
        )


@router.post(
    "/test-endpoint/project/{project_id}/auto-fix", response_model=TestResponsePayload
)
async def test_project_endpoint_with_auto_fix(
    project_id: str,
    payload: TestRequestPayload,
    auto_fix: bool = Query(
        True, description="Whether to automatically fix errors and retry"
    ),
    max_retries: int = Query(
        2, description="Maximum number of retry attempts for auto-fixing", ge=0, le=5
    ),
):
    """
    Test an endpoint within a generated project with automatic error fixing and retry capability.

    This endpoint will automatically detect runtime errors during testing and attempt to fix them
    by analyzing error messages, identifying the problematic files, and using AI to generate fixes.

    Supported error types:
    - Pydantic configuration errors (v1 to v2 migration)
    - Parameter mismatch errors (function signature issues)
    - Import errors
    - Generic runtime errors

    Args:
        project_id: The ID of the project containing the endpoint to test
        payload: The TestRequestPayload containing request details
        auto_fix: Whether to automatically fix errors and retry (default: True)
        max_retries: Maximum number of retry attempts for auto-fixing (default: 2, max: 5)

    Returns:
        TestResponsePayload: A structured response containing details of the test execution.
        If auto-fix was successful, this will contain the final successful response.
        If auto-fix failed, this will contain details about the last error encountered.
    """
    request_id = str(uuid.uuid4())
    logger.info(f"Received auto-fix test request for project: {project_id}")
    logger.info(f"Auto-fix enabled: {auto_fix}, Max retries: {max_retries}")
    logger.info(f"Original endpoint URL: {payload.endpointUrl}")
    logger.info(f"HTTP Method: {payload.httpMethod}")

    # Extract the endpoint path from the payload URL
    url = str(payload.endpointUrl)

    # Handle different URL formats
    if url.startswith("/"):
        # Simple path like "/health"
        path = url.lstrip("/")
    elif url.startswith(f"http://{project_id}/"):
        # Project-specific URL like "http://{project_id}/{path}"
        path = url.split("/", 3)[-1] if len(url.split("/", 3)) > 3 else ""
    else:
        # Assume it's just the path without leading slash
        path = url

    logger.info(f"Endpoint path: {path}")

    try:
        # Initialize the service to handle the testing logic
        test_service = TestEndpointService()

        # Execute the test with auto-fix capability
        response_data = await test_service.execute_test_with_auto_fix(
            project_id=project_id,
            path=path,
            payload=payload,
            request_id=request_id,
            auto_fix=auto_fix,
            max_retries=max_retries,
        )

        logger.info(
            f"Auto-fix test completed: {response_data.statusCode}, Success: {response_data.success}"
        )

        if response_data.success:
            return success_response(
                status_code=status.HTTP_200_OK,
                data=response_data,
                message="Request completed successfully with auto-fix",
            )
        else:
            # Auto-fix attempts failed, but we still return a structured response
            return success_response(
                status_code=status.HTTP_200_OK,  # We use 200 because the API call itself succeeded
                data=response_data,
                message="Request completed but auto-fix was unable to resolve all errors",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during auto-fix test execution: {str(e)}", exc_info=True)
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error during auto-fix test execution",
            detail=str(e),
        )


@router.post(
    "/test-endpoint/project/{project_id}/fix-code", response_model=CodeFixResponse
)
async def fix_project_code(project_id: str, payload: CodeFixPayload):
    """
    Fix code errors in a project file based on error context.

    This endpoint accepts error details and attempts to fix the code by analyzing
    the error message and applying AI-generated fixes to the specified file.

    Args:
        project_id: The ID of the project containing the file to fix
        payload: The CodeFixPayload containing error details and file information

    Returns:
        CodeFixResponse: A structured response containing the fix results"""
    request_id = str(uuid.uuid4())
    logger.info(f"[{request_id}] Received code fix request for project: {project_id}")
    logger.info(f"[{request_id}] File path: {payload.file_path}")
    logger.info(f"[{request_id}] Language: {payload.language}")
    logger.info(f"[{request_id}] Error message: {payload.error_message}")

    try:
        # Initialize the service to handle the code fixing
        test_service = (
            TestEndpointService()
        )  # Use the quality pipeline to intelligently identify the correct file to fix
        # if context contains traceback information
        actual_file_path = payload.file_path
        if payload.context and "Traceback" in payload.context:
            # Try to identify the actual problematic file from the traceback
            identified_file = test_service._identify_file_from_error(
                payload.context,
                project_id,
                (
                    payload.file_path.split("/")[-1]
                    if "/" in payload.file_path
                    else payload.file_path
                ),
            )
            if identified_file:
                logger.info(
                    f"Identified actual file with error: {identified_file} (instead of {payload.file_path})"
                )
                actual_file_path = identified_file
        elif "is not defined" in payload.error_message:
            # For "not defined" errors, try to find the file that actually has the undefined reference
            # Check if this is an import error that should be fixed in a model file
            if "ForeignKey" in payload.error_message:
                # Look for model files
                import glob

                project_path = f"repos/{project_id}"
                model_files = glob.glob(f"{project_path}/models/*.py")
                for model_file in model_files:
                    rel_path = os.path.relpath(model_file, project_path)
                    try:
                        with open(model_file, "r", encoding="utf-8") as f:
                            content = f.read()
                        if (
                            "ForeignKey" in content
                            and "from sqlalchemy import" in content
                        ):
                            logger.info(
                                f"Found ForeignKey usage in model file: {rel_path}"
                            )
                            actual_file_path = rel_path
                            break
                    except Exception as e:
                        logger.warning(f"Error reading {model_file}: {e}")
                        continue

        # Use the existing fix_code_error method from LangchainService
        from app.api.v1.services.langchain_service import LangchainService

        # Read the current file content
        project_path = f"repos/{project_id}"
        full_file_path = f"{project_path}/{actual_file_path}"

        if not os.path.exists(full_file_path):
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="File not found",
                detail=f"File {payload.file_path} does not exist in project {project_id}",
            )

        # Read the file content
        with open(full_file_path, "r", encoding="utf-8") as f:
            current_code = f.read()
        # Fix the code using LangchainService
        fix_result = await LangchainService.fix_code_error(
            project_id=project_id,
            error_message=payload.error_message,
            generated_code=current_code,
            language=payload.language,
            file_path=actual_file_path,
            context=payload.context,
        )

        fixed_code = fix_result.get("generated_code", "")

        if fixed_code and fixed_code.strip():
            # Write the fixed code back to the file
            with open(full_file_path, "w", encoding="utf-8") as f:
                f.write(fixed_code)

            response_data = CodeFixResponse(
                success=True,
                message="Code fixed successfully",
                fixed_code=fixed_code,
                file_path=actual_file_path,  # Return the actual file path that was fixed
                changes_applied=True,
            )

            logger.info(f"Code fix completed successfully for {actual_file_path}")
            return success_response(
                status_code=status.HTTP_200_OK,
                data=response_data,
                message="Code fixed successfully",
            )
        else:
            response_data = CodeFixResponse(
                success=False,
                message="Unable to generate fixed code",
                fixed_code=None,
                file_path=actual_file_path,
                changes_applied=False,
                error_details="No valid fix was generated",
            )

            return success_response(
                status_code=status.HTTP_200_OK,
                data=response_data,
                message="Code fix attempt completed but no changes were made",
            )

    except FileNotFoundError as e:
        logger.error(f"File not found: {str(e)}")
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="File not found",
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error during code fix: {str(e)}", exc_info=True)
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error during code fix",
            detail=str(e),
        )
