import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.api.v1.schemas.project_schemas import (
    SchemaContentSuccessResponse,
    SchemaListSuccessResponse,
    SchemaResponse,
)
from app.api.v1.services.project_schemas import GetAllSchemas
from app.api.v1.utils.error_response import error_response
from app.api.v1.utils.success_response import success_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["schemas"])


@router.get("/projects/{project_id}/schemas/", response_model=SchemaListSuccessResponse)
async def list_schemas(project_id: str):
    """
    Retrieves all schemas for a specific project from the repository
    Args:
        project_id: The slug of the project
    Returns:
        SchemaListSuccessResponse: List of schemas with their details
    Raises:
        HTTPException: If the project or schemas are not found or for server-side errors
    """
    try:
        schemas = await GetAllSchemas.get_all_schemas_from_repo(project_id)

        schema_responses = [
            SchemaResponse(
                name=schema["name"],
                description=schema.get("description", ""),
            )
            for schema in schemas
        ]

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Schemas Retrieved Successfully",
            data=schema_responses,
        )
    except ValueError as e:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Schemas not found",
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error retrieving schemas: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error retrieving schemas",
            detail=str(e),
        )


@router.get(
    "/projects/{project_id}/schemas/{schema_name}/content",
    response_model=SchemaContentSuccessResponse,
)
async def get_schema_content(project_id: str, schema_name: str):
    """
    Retrieves the content of a specific schema from a project repository
    Args:
        project_id: The slug of the project
        schema_name: The name of the schema (without .py extension)
    Returns:
        SchemaContentSuccessResponse: The schema content in both text and base64 formats, along with metadata
    Raises:
        HTTPException: If the project or schema is not found or for server-side errors
    """
    try:
        result = await GetAllSchemas.get_schema_content_from_repo(
            project_id, schema_name
        )

        if isinstance(result, JSONResponse):
            return result

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Schema Content Retrieved Successfully",
            data=result,
        )
    except Exception as e:
        logger.error(f"Error retrieving schema content: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error retrieving schema content",
            detail=str(e),
        )
