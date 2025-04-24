import base64
import logging

import requests
from fastapi import status

from app.api.v1.utils.error_response import error_response
from config import settings

logger = logging.getLogger(__name__)


class GetAllDocs:

    @staticmethod
    async def get_doc_content_from_repo(project_id: str, doc_name: str):
        """
        Retrieves the content of a specific markdown doc from a project repository.
        Only handles Markdown (.md) files for documentation.

        Args:
            project_id: The slug of the project
            doc_name: The name of the doc (with or without extension)
        Returns:
            The doc content in both text and base64 formats
        Raises:
            ValueError: If the project or doc is not found
            Exception: For any other errors
        """
        try:
            # Special case for test project - keeping as backward compatibility
            if project_id == "test-project" and doc_name == "deploy_doc":
                repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/docs/{doc_name}.md"
                response = requests.get(repo_api_url)

                if response.status_code == 200:
                    file_data = response.json()
                    content_base64 = file_data.get("content", "")
                    text_content = base64.b64decode(content_base64).decode("utf-8")

                    return {
                        "name": doc_name,
                        "format": "text",
                        "content": text_content,
                        "content_base64": content_base64,
                        "type": "markdown",
                    }

            # Handle file extensions
            base_doc_name = doc_name
            if doc_name.endswith(".md"):
                base_doc_name = doc_name.rsplit(".", 1)[0]
                doc_file = doc_name
                doc_type = "markdown"
            else:
                # If no extension, assume .md
                doc_file = f"{doc_name}.md"
                doc_type = "markdown"

            # Request the file from the repository
            repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/docs/{doc_file}"
            response = requests.get(repo_api_url)

            # Handle error responses
            if response.status_code == 404:
                return error_response(
                    status_code=status.HTTP_404_NOT_FOUND,
                    message="Documentation not found",
                    detail=f"Documentation '{doc_name}' not found in project {project_id}",
                )

            if response.status_code != 200:
                return error_response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="Failed to fetch documentation content",
                    detail=response.text,
                )

            # Parse the response and create the result
            file_data = response.json()
            content_base64 = file_data.get("content", "")

            try:
                text_content = base64.b64decode(content_base64).decode("utf-8")
            except Exception as e:
                logger.error(f"Error decoding content: {str(e)}")
                text_content = ""

            return {
                "name": base_doc_name,
                "format": "text",
                "content": text_content,
                "content_base64": content_base64,
                "type": doc_type,
            }

        except Exception as e:
            logger.error(f"Error retrieving doc content: {str(e)}")
            return error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Failed to fetch documentation content",
                detail=str(e),
            )
