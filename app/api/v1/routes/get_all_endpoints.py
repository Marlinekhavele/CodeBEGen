import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.db.database import get_db
from app.api.v1.schemas.endpoint_list_response import (
    EndpointListSuccessResponse,
    EndpointResponse,
)
from app.api.v1.services.get_all_endpoints import GetAllEndpoints
from app.api.v1.utils.error_response import error_response
from app.api.v1.utils.success_response import success_response

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["endpoints"])


@router.get(
    "/projects/{project_id}/endpoints", response_model=EndpointListSuccessResponse
)
async def list_endpoints(project_id: str, db: Session = Depends(get_db)):
    """
    Retrieves all endpoints for a specific project from the database

    Args:
        project_id: The slug of the project
        db: Database session

    Returns:
        EndpointListSuccessResponse: List of endpoints with their details

    Raises:
        ValueError: If the project or file is not found
        Exception: For any other server-side errors
    """
    try:
        endpoints = await GetAllEndpoints.get_all_endpoints_from_repo(project_id, db)

        # Transform to response schema
        endpoint_responses = [
            EndpointResponse(path=endpoint["path"], method=endpoint["method"])
            for endpoint in endpoints
        ]

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Endpoint Retrieved Succesfully",
            data=endpoint_responses,
        )
    except ValueError as e:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="File not found",
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error retrieving endpoints: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error retrieveing endpoints",
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unprocessable Enity: {str(e)}")
        return error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="Input data format is incorrect",
            detail=str(e),
        )
