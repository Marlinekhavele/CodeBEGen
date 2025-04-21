import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.api.v1.schemas.project_models import (
    ModelContentSuccessResponse,
    ModelListSuccessResponse,
    ModelResponse,
)
from app.api.v1.services.project_models import GetAllModels
from app.api.v1.utils.error_response import error_response
from app.api.v1.utils.success_response import success_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["models"])


@router.get("/projects/{project_id}/models/", response_model=ModelListSuccessResponse)
async def list_models(project_id: str):
    """
    Retrieves all models for a specific project from the repository

    Args:
        project_id: The slug of the project

    Returns:
        ModelListSuccessResponse: List of models with their details

    Raises:
        HTTPException: If the project or models are not found or for server-side errors
    """
    try:
        models = await GetAllModels.get_all_models_from_repo(project_id)

        # Check if models is a JSONResponse (error case)
        if isinstance(models, JSONResponse):
            return models

        model_responses = [
            ModelResponse(
                name=model["name"],
            )
            for model in models
        ]

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Models Retrieved Successfully",
            data=model_responses,
        )
    except ValueError as e:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Models not found",
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error retrieving models: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error retrieving models",
            detail=str(e),
        )


@router.get(
    "/projects/{project_id}/models/{model_name}/content",
    response_model=ModelContentSuccessResponse,
)
async def get_model_content(project_id: str, model_name: str):
    """
    Retrieves the content of a specific model from a project repository

    Args:
        project_id: The slug of the project
        model_name: The name of the model (without .py extension)

    Returns:
        ModelContentSuccessResponse: The model content in both text and base64 formats, along with metadata

    Raises:
        HTTPException: If the project or model is not found or for server-side errors
    """
    try:
        result = await GetAllModels.get_model_content_from_repo(project_id, model_name)

        if isinstance(result, JSONResponse):
            return result

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Model Content Retrieved Successfully",
            data=result,
        )
    except Exception as e:
        logger.error(f"Error retrieving model content: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error retrieving model content",
            detail=str(e),
        )
