import logging

from fastapi import APIRouter, status

from app.api.v1.schemas.project_db_migration import (
    MigrationRunData,
    MigrationRunSuccessResponse,
)
from app.api.v1.services.language_templates import LanguageTemplateFactory
from app.api.v1.utils.endpoint_services import get_project_dir_from_repo_url
from app.api.v1.utils.error_response import error_response
from app.api.v1.utils.git_utils import get_repo_url
from app.api.v1.utils.success_response import success_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["migration of database"])


@router.post(
    "/migration/{project_id}/run",
    response_model=MigrationRunSuccessResponse,
    status_code=status.HTTP_200_OK,
)
async def run_migrations(project_id: str):
    """
    Applies pending database migrations for the specified project.

    This endpoint runs all pending Alembic migrations for a project without generating new ones.
    It's intended to be called separately after code generation when the user is ready to apply
    database changes.

    Args:
        project_id (str): The project identifier

    Returns:
        MigrationRunSuccessResponse: Result of the migration operation including success status and message

    Raises:
        HTTPException: If migrations cannot be applied or the project is not found
    """
    try:
        # Get project_id
        repo_url = get_repo_url(project_id)
        if not repo_url:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Project not found",
                detail=f"No repository found for project ID: {project_id}",
            )

        project_dir = get_project_dir_from_repo_url(repo_url)

        # Create a PythonTemplate instance
        language_template = LanguageTemplateFactory.get_template("python")

        # Run the migrations
        result = await language_template.run_migrations(project_dir)

        # Prepare response data
        migration_data = MigrationRunData(
            success=result.get("success", False),
            message=result.get("message", "Migration execution completed"),
            database_path=result.get("database_path"),
        )
        # Check if migration was actually successful
        if not migration_data.success:
            return error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Migration execution failed",
                detail=migration_data.message,
            )
        # Return success response
        return success_response(
            status_code=status.HTTP_200_OK,
            message="Migration execution completed",
            data=migration_data,
        )

    except ValueError as e:
        # Handle specific errors like project not found
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Project not found",
            detail=str(e),
        )
    except Exception as e:
        # Log the error and return a server error response
        logger.error(f"Error in run_migrations endpoint: {str(e)}", exc_info=True)
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Migration execution failed",
            detail=str(e),
        )
