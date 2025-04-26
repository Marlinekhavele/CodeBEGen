import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.api.v1.schemas.project_migrations import (
    VersionContentSuccessResponse,
    VersionListSuccessResponse,
    VersionResponse,
)
from app.api.v1.services.project_migrations import GetAlembicVersions
from app.api.v1.utils.error_response import error_response
from app.api.v1.utils.success_response import success_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["alembic"])


@router.get(
    "/projects/{project_id}/alembic/versions/",
    response_model=VersionListSuccessResponse,
)
async def list_versions(project_id: str):
    """
    Retrieves all alembic migration versions for a specific project from the repository
    Args:
        project_id: The slug of the project
    Returns:
        VersionListSuccessResponse: List of alembic versions with their details
    Raises:
        HTTPException: If the project or versions are not found or for server-side errors
    """
    try:
        versions = await GetAlembicVersions.get_all_versions_from_repo(project_id)

        if isinstance(versions, JSONResponse):
            return versions

        version_responses = [
            VersionResponse(
                id=version["id"],
                name=version["name"],
                revision=version.get("revision"),
                filename=version["filename"],
                timestamp=version.get("timestamp"),
            )
            for version in versions
        ]

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Alembic Versions Retrieved Successfully",
            data=version_responses,
        )
    except ValueError as e:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Alembic versions not found",
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error retrieving alembic versions: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error retrieving alembic versions",
            detail=str(e),
        )


@router.get(
    "/projects/{project_id}/alembic/versions/{version_name}/content",
    response_model=VersionContentSuccessResponse,
)
async def get_version_content(project_id: str, version_name: str):
    """
    Retrieves the content of a specific alembic version from a project repository
    Args:
        project_id: The slug of the project
        version_id: The ID of the version (e.g., "0001")
    Returns:
        VersionContentSuccessResponse: The version content in both text and base64 formats, along with metadata
    Raises:
        HTTPException: If the project or version is not found or for server-side errors
    """
    try:
        result = await GetAlembicVersions.get_version_content_from_repo(
            project_id, version_name
        )

        if isinstance(result, JSONResponse):
            return result

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Alembic Version Content Retrieved Successfully",
            data=result,
        )
    except Exception as e:
        logger.error(f"Error retrieving version content: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to fetch version content",
            detail=str(e),
        )
