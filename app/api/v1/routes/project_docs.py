import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.api.v1.schemas.project_docs import DocsContentSuccessResponse
from app.api.v1.services.project_docs import GetAllDocs
from app.api.v1.utils.error_response import error_response
from app.api.v1.utils.success_response import success_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documentation"])


@router.get("/projects/{project_id}/docs/", response_model=DocsContentSuccessResponse)
async def list_docs(project_id: str):
    """
    Retrieves all documentation files for a specific project from the repository
    Args:
        project_id: The slug of the project
    Returns:
        DocsContentSuccessResponse: List of documentation files with their details
    Raises:
        HTTPException: If the project or documentation files are not found or for server-side errors
    """
    try:
        docs = await GetAllDocs.get_all_docs_from_repo(project_id)

        # Check if docs is a JSONResponse (error case)
        if isinstance(docs, JSONResponse):
            return docs

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Documentation Retrieved Successfully",
            data=docs,
        )
    except ValueError as e:
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Documentation not found",
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error retrieving documentation: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Error retrieving documentation",
            detail=str(e),
        )


@router.get(
    "/projects/{project_id}/docs/{doc_name}/content",
    response_model=DocsContentSuccessResponse,
)
async def get_doc_content(project_id: str, doc_name: str):
    """
    Retrieves the content of a specific documentation file from a project repository
    Args:
        project_id: The slug of the project
        doc_name: The name of the documentation file (with or without .md extension)
    Returns:
        DocContentSuccessResponse: The documentation content in both text and base64 formats, along with metadata
    Raises:
        HTTPException: If the project or documentation file is not found or for server-side errors
    """
    try:
        result = await GetAllDocs.get_doc_content_from_repo(project_id, doc_name)

        if isinstance(result, JSONResponse):
            return result

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Documentation Content Retrieved Successfully",
            data=result,
        )
    except Exception as e:
        logger.error(f"Error retrieving documentation content: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to fetch documentation content",
            detail=str(e),
        )
