import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.db.database import get_db
from app.api.v1.schemas.endpoints import EndpointFileRequest, EndpointSuccessResponse
from app.api.v1.services.endpoints import EndpointService
from app.api.v1.utils.error_response import error_response
from app.api.v1.utils.success_response import success_response

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/endpoint", tags=["endpoint"])


@router.get("/", response_model=EndpointSuccessResponse)
async def get_endpoint_file(
    project_id: str, endpoint_path: str, method: str, db: Session = Depends(get_db)
):
    """
    Get the content of an endpoint file.

    - **project_id**: The Project ID returned from project initialization
    - **endpoint_path**: The path of the endpoint (e.g., 'api/v1/endpoint')
    - **method**: The HTTP method for this endpoint (POST, GET, PUT, DELETE)
    - **description**: Optional description of the endpoint
    Returns the file content as base64-encoded string in the content_base64 field.
    """
    try:
        request = EndpointFileRequest(
            project_id=project_id, endpoint_path=endpoint_path, method=method
        )
        response = await EndpointService.get_file(request, db)
        return success_response(
            status_code=status.HTTP_200_OK,
            message="File retrieved successfully",
            data=response,
        )
    except ValueError as e:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="File not found",
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error retrieving file: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve file",
            detail=str(e),
        )


@router.post(
    "/", response_model=EndpointSuccessResponse, status_code=status.HTTP_201_CREATED
)
async def create_endpoint(request: EndpointFileRequest, db: Session = Depends(get_db)):
    """
    Create a new endpoint file.

    Request body:
    - **project_id**: The Project ID returned from project initialization
    - **endpoint_path**: The name of the endpoint (e.g., 'api/v1/endpoint')
    - **content_base64**: The content of the file as base64-encoded string
    - **method**: The HTTP method for this endpoint (POST, GET, PUT, DELETE)
    - **description**: Optional description of the endpoint
    """
    try:
        response = await EndpointService.create_endpoint(request, db)
        return success_response(
            status_code=status.HTTP_201_CREATED,
            message="File created successfully",
            data=response,
        )
    except ValueError as e:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="File not found",
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error creating file: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create file",
            detail=str(e),
        )


@router.put("/", response_model=EndpointSuccessResponse)
async def update_endpoint_file(request: EndpointFileRequest):
    """
    Update an existing endpoint file.

    Request body:
    - **project_id**: The Project ID returned from project initialization
    - **endpoint_path**: The name of the endpoint (e.g., 'api/v1/endpoint')
    - **content_base64**: The updated content of the file as base64-encoded string
    - **method**: The HTTP method for this endpoint (POST, GET, PUT, DELETE)
    - **description**: Optional description of the endpoint

    """
    try:
        response = await EndpointService.update_file(request)
        return success_response(
            status_code=status.HTTP_200_OK,
            message="File updated successfully",
            data=response,
        )
    except ValueError as e:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="File not found",
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error updating file: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update file",
            detail=str(e),
        )


@router.delete("/", response_model=EndpointSuccessResponse)
async def delete_endpoint_file(
    project_id: str = Query(
        ..., description="Project ID returned from project initialization"
    ),
    endpoint_path: str = Query(
        ..., description="Path of the endpoint to delete (e.g., 'api/v1/endpoint')"
    ),
    method: str = Query(
        ..., description="HTTP method for this endpoint (GET, POST, PUT, DELETE)"
    ),
    description: Optional[str] = Query(
        None, description="Optional description of the endpoint"
    ),
    db: Session = Depends(get_db),
):
    """
    Delete an endpoint file.

    - **project_id**: The Project ID returned from project initialization
    - **endpoint_path**: The path of the endpoint to delete
    - **method**: The HTTP method for this endpoint (GET, POST, PUT, DELETE)
    - **description**: Optional description of the endpoint

    Returns:
        Confirmation of endpoint deletion with commit hash and file details
    """
    try:
        request = EndpointFileRequest(
            project_id=project_id,
            endpoint_path=endpoint_path,
            method=method,
            description=description,
        )

        response = await EndpointService.delete_file(request, db)

        return success_response(
            status_code=status.HTTP_200_OK,
            message="File deleted successfully",
            data=response,
        )
    except ValueError as ve:
        # Handle specific error cases with appropriate status codes
        error_message = str(ve).lower()

        if "critical system endpoint" in error_message:
            return error_response(
                status_code=status.HTTP_403_FORBIDDEN,
                message="Cannot delete critical system endpoint",
                detail=str(ve),
            )
        elif "not found" in error_message:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="File not found",
                detail=str(ve),
            )
        elif "database error" in error_message:
            return error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Database error",
                detail=str(ve),
            )
        else:
            return error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Invalid request",
                detail=str(ve),
            )
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete file",
            detail=str(e),
        )
