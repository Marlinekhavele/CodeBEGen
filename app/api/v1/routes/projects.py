import logging
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

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


@router.get("/export/")
async def download_repository_file(
    project_name: str = Query(..., description="Repository name to download"),
    output_filename: Optional[str] = Query(
        None, description="Custom filename for download"
    ),
):
    """
    Downloads a repository from Gitea and returns it as a file download response.
    This endpoint will trigger the browser's download dialog.

    Args:
        project_name: Name of the repository to download
        output_filename: Optional custom filename for the downloaded file

    Returns:
        FileResponse that will prompt the browser to download the file
    """
    try:
        # Create a temporary file that will persist until the response is sent
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        temp_file.close()
        temp_path = Path(temp_file.name)

        try:
            # Download the repository directly to the temporary file
            await ProjectInitService.download_project_gitea_repo(
                project_name, temp_path
            )

            # Determine the filename for the download
            filename = output_filename if output_filename else f"{project_name}.zip"

            # Return a FileResponse which will trigger the browser's file download
            response = FileResponse(
                path=temp_path, filename=filename, media_type="application/zip"
            )

            # Set up a background task to delete the file after the response is sent
            def cleanup_temp_file():
                try:
                    if temp_path.exists():
                        temp_path.unlink()
                except Exception as e:
                    logger.error(f"Failed to delete temporary file: {e}")

            # Attach the cleanup function to the response's background tasks
            response.background = BackgroundTask(cleanup_temp_file)

            return response

        except Exception as e:
            # Clean up the temporary file in case of an error
            if temp_path.exists():
                temp_path.unlink()
            raise e

    except HTTPException as http_ex:
        # Re-raise FastAPI HTTP exceptions
        raise http_ex

    except Exception as e:
        logger.exception(f"Failed to download repository: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to download repository",
            detail=str(e),
        )
