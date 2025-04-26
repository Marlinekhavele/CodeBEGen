import base64
import logging
import re
from datetime import datetime

import requests
from fastapi import status

from app.api.v1.utils.error_response import error_response
from config import settings

logger = logging.getLogger(__name__)


class GetAlembicVersions:
    @staticmethod
    async def get_all_versions_from_repo(project_id: str):
        """
        Retrieves all alembic migration versions from a specific project repository
        Args:
            project_id: The slug of the project
        Returns:
            List of alembic versions
        Raises:
            ValueError: If the project or versions directory is not found
            Exception: For any other errors
        """
        try:
            repo_versions_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/alembic/versions"

            response = requests.get(repo_versions_url)

            if response.status_code == 404:
                return error_response(
                    status_code=status.HTTP_404_NOT_FOUND,
                    message="Alembic versions directory not found",
                    detail=f"Alembic versions directory not found in project {project_id}",
                )

            if response.status_code != 200:
                return error_response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="Failed to fetch alembic versions",
                    detail=response.text,
                )

            contents = response.json()

            versions = []
            for item in contents:
                if (
                    item["type"] == "file"
                    and item["name"].endswith(".py")
                    and not item["name"].startswith("_")
                    and "__pycache__" not in item["path"]
                ):
                    # Extract version id from filename (e.g., "0001_initial.py" -> "0001")
                    version_id = item["name"].split("_")[0]

                    # Get migration description (e.g., "0001_initial.py" -> "initial")
                    migration_name = "_".join(item["name"].split("_")[1:]).replace(
                        ".py", ""
                    )

                    # Get file metadata to extract timestamp
                    file_response = requests.get(item["url"])
                    timestamp = None
                    revision = None

                    if file_response.status_code == 200:
                        file_data = file_response.json()
                        content_base64 = file_data.get("content", "")

                        try:
                            text_content = base64.b64decode(content_base64).decode(
                                "utf-8"
                            )

                            # Extract revision using regex
                            revision_match = re.search(
                                r"revision\s*=\s*['\"]([^'\"]+)['\"]", text_content
                            )
                            if revision_match:
                                revision = revision_match.group(1)

                            # Try to extract timestamp if present in the file
                            timestamp_match = re.search(
                                r"create_date\s*=\s*['\"]([^'\"]+)['\"]", text_content
                            )
                            if timestamp_match:
                                timestamp_str = timestamp_match.group(1)
                                try:
                                    # Parse the timestamp string to a datetime object
                                    timestamp = datetime.fromisoformat(
                                        timestamp_str
                                    ).isoformat()
                                except ValueError:
                                    logger.warning(
                                        f"Could not parse timestamp: {timestamp_str}"
                                    )
                        except Exception as e:
                            logger.error(f"Error processing file content: {str(e)}")

                    versions.append(
                        {
                            "id": version_id,
                            "name": migration_name,
                            "filename": item["name"],
                            "path": item["path"],
                            "url": item["html_url"],
                            "size": item["size"],
                            "timestamp": timestamp,
                            "revision": revision,
                        }
                    )

            # Sort versions by id to ensure chronological order
            versions.sort(key=lambda x: x["id"])
            return versions

        except ValueError as e:
            logger.error(f"Value Error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error retrieving alembic versions: {str(e)}")
            raise

    @staticmethod
    async def get_version_content_from_repo(project_id: str, version_name: str):
        """
        Retrieves the content of a specific alembic version from a project repository
        Args:
            project_id: The slug of the project
            version_name: The name of the version (e.g., "german_table") without ID prefix
        Returns:
            The version content and metadata
        Raises:
            ValueError: If the project or version is not found
            Exception: For any other errors
        """
        try:
            # First get all versions to find the one with matching name
            all_versions = await GetAlembicVersions.get_all_versions_from_repo(
                project_id
            )

            if isinstance(all_versions, dict) and "status_code" in all_versions:
                # Error response already formatted
                return all_versions

            # Find the version with matching name
            version = next((v for v in all_versions if v["name"] == version_name), None)

            if not version:
                return error_response(
                    status_code=status.HTTP_404_NOT_FOUND,
                    message="Version not found",
                    detail=f"Alembic version '{version_name}' not found in project {project_id}",
                )

            # Use the full path from the version metadata (which is the correct path)
            repo_api_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/{version['path']}"
            response = requests.get(repo_api_url)

            if response.status_code != 200:
                return error_response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="Failed to fetch version content",
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

            result = {
                "id": version["id"],
                "name": version["name"],
                "revision": version["revision"],
                "filename": version["filename"],
                "format": "text",
                "content": text_content,
                "content_base64": content_base64,
                "timestamp": version["timestamp"],
            }

            return result

        except Exception as e:
            logger.error(f"Error retrieving version content: {str(e)}")
            return error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Failed to fetch version content",
                detail=str(e),
            )
