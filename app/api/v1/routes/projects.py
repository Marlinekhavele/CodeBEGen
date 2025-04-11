import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.db.database import get_db
from app.api.v1.schemas.projects import ProjectInitRequest, ProjectInitSuccessResponse
from app.api.v1.services.projects import ProjectInitService
from app.api.v1.utils.error_response import error_response
from app.api.v1.utils.success_response import success_response

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define router
router = APIRouter(prefix="/project-url", tags=["project"])


@router.post(
    "/", response_model=ProjectInitSuccessResponse, status_code=status.HTTP_201_CREATED
)
async def initialize_project(
    init_request: ProjectInitRequest, db: Session = Depends(get_db)
):
    """
    Initializes a new project with the given name and creates repository URLs

    Args:
        init_request: Request object containing project name and other initialization parameters
        db: Database session for persistence operations

    Returns:
        ProjectInitSuccessResponse: Success response containing repository URL and project URL

    Raises:
        Exception: If project initialization fails for any reason
    """
    try:
        logger.info(f"Received request with project_name: {init_request.project_name}")

        response = await ProjectInitService.initialize_project(init_request, db)
        logger.info(f"Project initialization completed. Response: {response}")
        return success_response(
            status_code=status.HTTP_201_CREATED,
            message="Project initialized successfully",
            data=response,
        )

    except Exception as e:
        logger.error(f"Error initializing project: {str(e)}", exc_info=True)
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to initialize project",
            detail=str(e),
        )
