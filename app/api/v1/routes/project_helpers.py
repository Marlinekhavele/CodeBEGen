import logging
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from app.api.v1.utils.success_response import success_response
from app.api.v1.utils.error_response import error_response
from app.api.v1.schemas.project_helpers import (
    HelperResponse, 
    HelperListSuccessResponse, 
    HelperContentSuccessResponse
)
from app.api.v1.services.project_helpers import GetAllHelpers

logger = logging.getLogger(__name__)

router = APIRouter(tags=["helpers"])

@router.get("/projects/{project_id}/helpers/", response_model=HelperListSuccessResponse)
async def list_helpers(project_id: str):
    """
    Retrieves all helpers for a specific project from the repository
    Args:
        project_id: The slug of the project
    Returns:
        HelperListSuccessResponse: List of helpers with their details
    Raises:
        HTTPException: If the project or helpers are not found or for server-side errors
    """
    try:
        helpers = await GetAllHelpers.get_all_helpers_from_repo(project_id)
        
        if isinstance(helpers, JSONResponse):
            return helpers

        helper_responses = [
            HelperResponse(
                name=helper["name"],
                description=helper.get("description", ""),
                type=helper.get("type", "") 
            ) for helper in helpers
        ]

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Helpers Retrieved Successfully",
            data=helper_responses
        )
    except ValueError as e:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Helpers not found",
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error retrieving helpers: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error retrieving helpers",
            detail=str(e)
        )

@router.get("/projects/{project_id}/helpers/{helper_name}/content", response_model=HelperContentSuccessResponse)
async def get_helper_content(project_id: str, helper_name: str):
    """
    Retrieves the content of a specific helper from a project repository
    Args:
        project_id: The slug of the project
        helper_name: The name of the helper (without .py extension)
    Returns:
        HelperContentSuccessResponse: The helper content in both text and base64 formats, along with metadata
    Raises:
        HTTPException: If the project or helper is not found or for server-side errors
    """
    try:
        result = await GetAllHelpers.get_helper_content_from_repo(project_id, helper_name)

        if isinstance(result, JSONResponse):
            return result

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Helper Content Retrieved Successfully",
            data=result
        )
    except Exception as e:
        logger.error(f"Error retrieving helper content: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to fetch helper content",
            detail=str(e)
        )