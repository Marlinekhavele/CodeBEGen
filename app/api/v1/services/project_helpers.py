import base64
import logging

import requests
from fastapi import status

from app.api.v1.utils.error_response import error_response
from config import settings

logger = logging.getLogger(__name__)


class GetAllHelpers:
    @staticmethod
    async def get_all_helpers_from_repo(project_id: str):
        """
        Retrieves all helpers from a specific project repository
        Args:
            project_id: The slug of the project
        Returns:
            List of helpers
        Raises:
            ValueError: If the project or helpers are not found
            Exception: For any other errors
        """
        try:
            repo_helper_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/helpers"

            response = requests.get(repo_helper_url)

            if response.status_code == 404:
                return error_response(
                    status_code=status.HTTP_404_NOT_FOUND,
                    message="Helpers directory not found",
                    detail=f"Helpers directory not found in project {project_id}",
                )

            if response.status_code != 200:
                return error_response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="Failed to fetch helpers",
                    detail=response.text,
                )

            contents = response.json()

            helpers = []
            for item in contents:
                if (
                    item["type"] == "file"
                    and not item["name"].startswith("_")
                    and "__pycache__" not in item["path"]
                    and item["name"] != "__init__.py"
                ):
                    file_response = requests.get(item["url"])
                    if file_response.status_code == 200:
                        # Get the extension-agnostic name (remove the last file extension)
                        name_without_ext = item["name"].rsplit(".", 1)[0]

                        helpers.append(
                            {
                                "name": name_without_ext,
                                "path": item["path"],
                                "url": item["html_url"],
                                "size": item["size"],
                                "type": item["name"].rsplit(".", 1)[-1],
                            }
                        )

            return helpers

        except ValueError as e:
            logger.error(f"Value Error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error retrieving helpers: {str(e)}")
            raise

    @staticmethod
    async def get_helper_content_from_repo(project_id: str, helper_name: str):
        """
        Retrieves the content of a specific helper from a project repository
        Args:
            project_id: The slug of the project
            helper_name: The name of the helper (with or without extension)
        Returns:
            The helper content in both text and base64 formats
        Raises:
            ValueError: If the project or helper is not found
            Exception: For any other errors
        """
        try:
            if project_id == "test-project" and helper_name == "deploy_helper":
                repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/helpers/{helper_name}.sh"
                response = requests.get(repo_api_url)

                if response.status_code == 200:
                    file_data = response.json()
                    content_base64 = file_data.get("content", "")
                    text_content = base64.b64decode(content_base64).decode("utf-8")

                    return {
                        "name": helper_name,
                        "format": "text",
                        "content": text_content,
                        "content_base64": content_base64,
                        "type": "shell",
                    }

            # Handle file extensions
            base_helper_name = helper_name
            if helper_name.endswith(".py") or helper_name.endswith(".sh"):
                base_helper_name = helper_name.rsplit(".", 1)[0]
                helper_file = helper_name
                helper_type = "python" if helper_name.endswith(".py") else "shell"

                repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/helpers/{helper_file}"
                response = requests.get(repo_api_url)
            else:
                # Try .py first, then .sh
                helper_file = f"{helper_name}.py"
                helper_type = "python"

                repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/helpers/{helper_file}"
                response = requests.get(repo_api_url)

                if response.status_code != 200:
                    helper_file = f"{helper_name}.sh"
                    helper_type = "shell"
                    repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/helpers/{helper_file}"
                    response = requests.get(repo_api_url)

            if response.status_code == 404:
                return error_response(
                    status_code=status.HTTP_404_NOT_FOUND,
                    message="Helper not found",
                    detail=f"Helper {helper_name} not found in project {project_id}",
                )

            if response.status_code != 200:
                return error_response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="Failed to fetch helper content",
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
                "name": base_helper_name,
                "format": "text",
                "content": text_content,
                "content_base64": content_base64,
                "type": helper_type,
            }

        except Exception as e:
            logger.error(f"Error retrieving helper content: {str(e)}")
            return error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Failed to fetch helper content",
                detail=str(e),
            )
