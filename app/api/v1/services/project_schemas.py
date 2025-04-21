import base64
import logging
import requests
from fastapi import status
from app.api.v1.utils.error_response import error_response
from config import settings

logger = logging.getLogger(__name__)

class GetAllSchemas:
    @staticmethod
    async def get_all_schemas_from_repo(project_id: str):
        """
        Retrieves all schemas from a specific project repository
        Args:
            project_id: The slug of the project
        Returns:
            List of schemas
        Raises:
            ValueError: If the project or schemas are not found
            Exception: For any other errors
        """
        try:
            repo_schema_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/schemas"

            response = requests.get(repo_schema_url)

            if response.status_code == 404:
                return error_response(
                    status_code=status.HTTP_404_NOT_FOUND,
                    message=f"Schemas directory not found in project {project_id}",
                    detail="The schemas directory does not exist in this repository"
                )

            if response.status_code != 200:
                return error_response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="Failed to fetch schemas",
                    detail=response.text
                )

            contents = response.json()

            schemas = []
            for item in contents:
                if (item["type"] == "file" and
                        item["name"].endswith(".py") and  # Look for .py files
                        item["name"] != "__init__.py" and
                        not item["name"].startswith("_") and
                        "__pycache__" not in item["path"]):

                    file_response = requests.get(item["url"])
                    if file_response.status_code == 200:
                        schemas.append({
                            "name": item["name"].replace(".py", ""), # Remove .py extension
                            "path": item["path"],
                            "url": item["html_url"],
                            "size": item["size"]
                        })

            return schemas

        except ValueError as e:
            logger.error(f"Value Error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error retrieving schemas: {str(e)}")
            raise
        
    @staticmethod   
    async def get_schema_content_from_repo(project_id: str, schema_name: str):
        """
        Retrieves the content of a specific schema from a project repository
        Args:
            project_id: The slug of the project
            schema_name: The name of the schema (without .py extension)
        Returns:
            The schema content in both text and base64 formats
        Raises:
            ValueError: If the project or schema is not found
            Exception: For any other errors
        """
        try:
            if not schema_name.endswith(".py"):
                schema_file = f"{schema_name}.py"
            else:
                schema_file = schema_name
                schema_name = schema_name[:-3]  # Remove .py extension for response

            repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/schemas/{schema_file}"

            response = requests.get(repo_api_url)

            if response.status_code == 404:
                return error_response(
                    status_code=status.HTTP_404_NOT_FOUND,
                    message=f"Schema {schema_name} not found in project {project_id}",
                    detail="The specified schema does not exist in this repository"
                )

            if response.status_code != 200:
                return error_response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="Failed to fetch schema content",
                    detail=response.text
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
                "name": schema_name,
                "format": "text",
                "content": text_content,
                "content_base64": content_base64
            }

        except Exception as e:
            logger.error(f"Error retrieving schema content: {str(e)}")
            return error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Error retrieving schema content",
                detail=str(e)
            )

