import base64
import logging

import requests
from fastapi import status

from app.api.v1.utils.error_response import error_response
from config import settings

logger = logging.getLogger(__name__)


class GetAllModels:
    @staticmethod
    async def get_all_models_from_repo(project_id: str):
        """
        Retrieves all models from a specific project repository

        Args:
            project_id: The slug of the project

        Returns:
            List of models

        Raises:
            ValueError: If the project or models are not found
            Exception: For any other errors
        """
        try:
            repo_model_url = (
                f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/models"
            )

            response = requests.get(repo_model_url)

            if response.status_code == 404:
                return error_response(
                    status_code=status.HTTP_404_NOT_FOUND,
                    message=f"Models directory not found in project {project_id}",
                    detail="The models directory does not exist in this repository",
                )

            if response.status_code != 200:
                return error_response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="Failed to fetch models",
                    detail=response.text,
                )

            # Parse the response
            contents = response.json()

            # Filter for model files (excluding __init__.py and other package files)
            models = []
            for item in contents:
                if (
                    item["type"] == "file"
                    and item["name"].endswith(".py")
                    and item["name"] != "__init__.py"
                    and not item["name"].startswith("_")
                    and "__pycache__" not in item["path"]
                ):

                    # Check if we can access the file (validates it exists and we have permissions)
                    file_response = requests.get(item["url"])
                    if file_response.status_code == 200:
                        models.append(
                            {
                                "name": item["name"].replace(".py", ""),
                                "path": item["path"],
                                "url": item["html_url"],
                                "size": item["size"],
                            }
                        )

            return models

        except ValueError as e:
            logger.error(f"Value Error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error retrieving models: {str(e)}")
            raise

    @staticmethod
    async def get_model_content_from_repo(
        project_id: str,
        model_name: str,
    ):
        """
        Retrieves the content of a specific model from a project repository

        Args:
            project_id: The slug of the project
            model_name: The name of the model (without .py extension)

        Returns:
            The model content in both text and base64 formats

        Raises:
            ValueError: If the project or model is not found
            Exception: For any other errors
        """
        try:
            if not model_name.endswith(".py"):
                model_file = f"{model_name}.py"
            else:
                model_file = model_name
                model_name = model_name[:-3]  # Remove .py extension for response

            repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/models/{model_file}"

            response = requests.get(repo_api_url)

            if response.status_code == 404:
                return error_response(
                    status_code=status.HTTP_404_NOT_FOUND,
                    message=f"Model {model_name} not found in project {project_id}",
                    detail="The specified model does not exist in this repository",
                )

            if response.status_code != 200:
                return error_response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="Failed to fetch model content",
                    detail=response.text,
                )

            # Parse the response
            file_data = response.json()

            content_base64 = file_data.get("content", "")

            # Remove any newlines that might be in the base64 string
            content_base64 = content_base64.replace("\n", "")

            # Decode the Base64 to get text content
            try:
                text_content = base64.b64decode(content_base64).decode("utf-8")
            except Exception as e:
                logger.error(f"Error decoding content: {str(e)}")
                text_content = ""

            return {
                "name": model_name,
                "format": "text",
                "content": text_content,
                "content_base64": content_base64,
            }

        except Exception as e:
            logger.error(f"Error retrieving model content: {str(e)}")
            return error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Error retrieving model content",
                detail=str(e),
            )
