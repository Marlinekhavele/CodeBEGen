import logging

from fastapi import APIRouter, Query, status

from app.api.v1.schemas.project_structure import (
    FileContentSuccessResponse,
    ProjectModulesSuccessResponse,
    ProjectStructureSuccessResponse,
    SearchResultsSuccessResponse,
)
from app.api.v1.services.project_structure import ProjectStructureService
from app.api.v1.utils.error_response import error_response
from app.api.v1.utils.success_response import success_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["project-structure"])


@router.get(
    "/projects/{project_id}/structure",
    response_model=ProjectStructureSuccessResponse,
)
async def get_project_structure(project_id: str):
    """
    Get the full file structure for a specific project.

    Args:
        project_id: The slug of the project

    Returns:
        Complete directory/file structure of the project

    Raises:
        404: If the project is not found
        500: For any server-side errors
    """
    try:
        response = await ProjectStructureService.get_project_structure(project_id)

        if "error" in response:
            return response

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Project structure retrieved successfully",
            data=response["data"],
        )
    except ValueError as e:
        logger.error(f"Error retrieving project structure: {str(e)}")
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Project not found",
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error retrieving project structure: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve project structure",
            detail=str(e),
        )


@router.get(
    "/projects/{project_id}/modules",
    response_model=ProjectModulesSuccessResponse,
)
async def get_project_modules(project_id: str):
    """
    Get all modules (categorized by type) in a project.

    Args:
        project_id: The slug of the project

    Returns:
        Dictionary of project modules categorized by type

    Raises:
        404: If the project is not found
        500: For any server-side errors
    """
    try:
        response = await ProjectStructureService.get_project_modules(project_id)

        if "error" in response:
            return response

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Project modules retrieved successfully",
            data=response["data"],
        )
    except ValueError as e:
        logger.error(f"Error retrieving project modules: {str(e)}")
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Project not found",
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error retrieving project modules: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve project modules",
            detail=str(e),
        )


@router.get(
    "/projects/{project_id}/file-content",
    response_model=FileContentSuccessResponse,
)
async def get_file_content(
    project_id: str,
    file_path: str = Query(..., description="Relative path to the file"),
):
    """
    Get the content of a specific file in the project.

    Args:
        project_id: The slug of the project
        file_path: Relative path to the file from the project root

    Returns:
        File content in both text and base64 formats

    Raises:
        404: If the project or file is not found
        400: If the path is not a file
        500: For any server-side errors
    """
    try:
        response = await ProjectStructureService.get_file_content(project_id, file_path)

        if "error" in response:
            return response

        return success_response(
            status_code=status.HTTP_200_OK,
            message="File content retrieved successfully",
            data=response["data"],
        )
    except ValueError as e:
        logger.error(f"Error retrieving file content: {str(e)}")
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Project or file not found",
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error retrieving file content: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve file content",
            detail=str(e),
        )


@router.get(
    "/projects/{project_id}/search",
    response_model=SearchResultsSuccessResponse,
)
async def search_project_files(
    project_id: str, query: str = Query(..., description="Search query")
):
    """
    Search across files in the project for a specific query.

    Args:
        project_id: The slug of the project
        query: The search query

    Returns:
        List of search results with context

    Raises:
        404: If the project is not found
        400: If the search query is empty
        500: For any server-side errors
    """
    try:
        response = await ProjectStructureService.search_project_files(project_id, query)

        if "error" in response:
            return response

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Search completed successfully",
            data=response["data"],
        )
    except ValueError as e:
        logger.error(f"Error searching project files: {str(e)}")
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Project not found",
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error searching project files: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to search project files",
            detail=str(e),
        )
