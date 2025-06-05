import base64
import logging
from pathlib import Path
from typing import Any, Dict, List

from fastapi import status

from app.api.v1.utils.endpoint_services import get_project_dir_from_repo_url
from app.api.v1.utils.error_response import error_response
from app.api.v1.utils.git_utils import get_repo_url

logger = logging.getLogger(__name__)


class ProjectStructureService:
    @staticmethod
    async def get_project_structure(project_id: str) -> Dict[str, Any]:
        """
        Get the complete file structure for a project.

        Args:
            project_id: The slug of the project

        Returns:
            Dict containing the project structure

        Raises:
            ValueError: If the project is not found
            Exception: For any other errors
        """
        try:
            # Get project directory
            repo_url = get_repo_url(project_id)
            project_dir = get_project_dir_from_repo_url(repo_url)

            if not project_dir.exists():
                return error_response(
                    status_code=status.HTTP_404_NOT_FOUND,
                    message=f"Project {project_id} not found",
                    detail="The project directory does not exist",
                )

            # Build the structure recursively
            structure = ProjectStructureService._build_directory_structure(project_dir)

            return {
                "status_code": status.HTTP_200_OK,
                "message": "Project structure retrieved successfully",
                "data": {"project_id": project_id, "structure": structure},
            }

        except ValueError as e:
            logger.error(f"Value Error: {str(e)}")
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

    @staticmethod
    def _build_directory_structure(directory_path: Path) -> Dict[str, Any]:
        """
        Recursively build a dictionary representing the directory structure.

        Args:
            directory_path: Path to the directory

        Returns:
            Dictionary with directory structure
        """
        structure = {
            "type": "directory",
            "name": directory_path.name,
            "path": str(directory_path),
            "children": [],
        }

        try:
            for item in directory_path.iterdir():
                # Skip __pycache__ directories and .git directory
                if "__pycache__" in str(item) or ".git" in str(item):
                    continue

                if item.is_dir():
                    # Recursively process subdirectories
                    child_structure = (
                        ProjectStructureService._build_directory_structure(item)
                    )
                    structure["children"].append(child_structure)
                else:
                    # Add file info
                    file_info = {
                        "type": "file",
                        "name": item.name,
                        "path": str(item),
                        "extension": item.suffix.lstrip("."),
                        "size": item.stat().st_size,
                    }
                    structure["children"].append(file_info)

            # Sort children by name with directories first
            structure["children"].sort(
                key=lambda x: (x["type"] != "directory", x["name"])
            )
            return structure

        except Exception as e:
            logger.error(
                f"Error building directory structure for {directory_path}: {str(e)}"
            )
            return structure

    @staticmethod
    async def get_project_modules(project_id: str) -> Dict[str, Any]:
        """
        Get all modules (Python files, JavaScript files, etc.) in a project.

        Args:
            project_id: The slug of the project

        Returns:
            Dict containing the project modules categorized by type

        Raises:
            ValueError: If the project is not found
            Exception: For any other errors
        """
        try:
            # Get project directory
            repo_url = get_repo_url(project_id)
            project_dir = get_project_dir_from_repo_url(repo_url)

            if not project_dir.exists():
                return error_response(
                    status_code=status.HTTP_404_NOT_FOUND,
                    message=f"Project {project_id} not found",
                    detail="The project directory does not exist",
                )

            # Categorize modules by type
            modules = {
                "models": [],
                "endpoints": [],
                "schemas": [],
                "utils": [],
                "controllers": [],
                "routes": [],
                "helpers": [],
                "others": [],
            }

            # Process the project directory
            await ProjectStructureService._gather_modules(
                project_dir, modules, project_dir
            )

            return {
                "status_code": status.HTTP_200_OK,
                "message": "Project modules retrieved successfully",
                "data": {"project_id": project_id, "modules": modules},
            }

        except ValueError as e:
            logger.error(f"Value Error: {str(e)}")
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

    @staticmethod
    async def _gather_modules(
        directory_path: Path,
        modules: Dict[str, List[Dict[str, Any]]],
        project_root: Path,
    ) -> None:
        """
        Recursively gather modules from the directory and categorize them.

        Args:
            directory_path: Path to the directory
            modules: Dict to store categorized modules
            project_root: Root path of the project for relative paths
        """
        try:
            for item in directory_path.iterdir():
                # Skip __pycache__ directories and .git directory
                if "__pycache__" in str(item) or ".git" in str(item):
                    continue

                if item.is_dir():
                    # Recursively process subdirectories
                    await ProjectStructureService._gather_modules(
                        item, modules, project_root
                    )
                else:
                    # Create relative path from project root
                    rel_path = item.relative_to(project_root)

                    # Basic file info
                    file_info = {
                        "name": item.name,
                        "path": str(rel_path),
                        "full_path": str(item),
                        "extension": item.suffix.lstrip("."),
                    }

                    # Categorize by directory or extension
                    if "models" in str(rel_path):
                        modules["models"].append(file_info)
                    elif "endpoints" in str(rel_path) or "api" in str(rel_path):
                        modules["endpoints"].append(file_info)
                    elif "schemas" in str(rel_path):
                        modules["schemas"].append(file_info)
                    elif "utils" in str(rel_path):
                        modules["utils"].append(file_info)
                    elif "controllers" in str(rel_path):
                        modules["controllers"].append(file_info)
                    elif "routes" in str(rel_path):
                        modules["routes"].append(file_info)
                    elif "helpers" in str(rel_path):
                        modules["helpers"].append(file_info)
                    elif item.suffix in [".py", ".js", ".ts"]:
                        modules["others"].append(file_info)
        except Exception as e:
            logger.error(f"Error gathering modules from {directory_path}: {str(e)}")

    @staticmethod
    async def get_file_content(project_id: str, file_path: str) -> Dict[str, Any]:
        """
        Get the content of a specific file in the project.

        Args:
            project_id: The slug of the project
            file_path: Relative path to the file from the project root

        Returns:
            Dict containing the file content in text and base64 formats

        Raises:
            ValueError: If the project or file is not found
            Exception: For any other errors
        """
        try:
            # Get project directory
            repo_url = get_repo_url(project_id)
            project_dir = get_project_dir_from_repo_url(repo_url)

            if not project_dir.exists():
                return error_response(
                    status_code=status.HTTP_404_NOT_FOUND,
                    message=f"Project {project_id} not found",
                    detail="The project directory does not exist",
                )
            # Normalize file path
            normalized_path = file_path.replace("\\", "/").lstrip("/")
            # The issue might be here - log the paths for debugging
            logger.info(f"Original file_path: {file_path}")
            logger.info(f"Normalized path: {normalized_path}")
            logger.info(f"Project dir: {project_dir}")

            # If normalized_path starts with 'repos/project_id', remove that prefix
            # as project_dir already points to the project directory
            prefix = f"repos/{project_id}"
            if normalized_path.startswith(prefix):
                normalized_path = normalized_path[len(prefix) :].lstrip("/")
                logger.info(f"Adjusted normalized path: {normalized_path}")

            full_path = project_dir / normalized_path
            logger.info(f"Full path: {full_path}")

            if not full_path.exists():
                return error_response(
                    status_code=status.HTTP_404_NOT_FOUND,
                    message=f"File not found: {file_path}",
                    detail=f"The file {file_path} does not exist in project {project_id}",
                )

            if not full_path.is_file():
                return error_response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="Not a file",
                    detail=f"{file_path} is not a file",
                )

            # Get file extension
            file_extension = full_path.suffix.lstrip(".")

            # Read file content
            try:
                # Handle binary files
                if file_extension in ["png", "jpg", "jpeg", "gif", "pdf", "zip"]:
                    with open(full_path, "rb") as f:
                        content = f.read()
                    text_content = "Binary file"
                    content_base64 = base64.b64encode(content).decode("utf-8")
                else:
                    # Handle text files
                    with open(full_path, "r", encoding="utf-8") as f:
                        text_content = f.read()
                    content_base64 = base64.b64encode(
                        text_content.encode("utf-8")
                    ).decode("utf-8")
            except UnicodeDecodeError:
                # If text reading fails, treat as binary
                with open(full_path, "rb") as f:
                    content = f.read()
                text_content = "Binary file"
                content_base64 = base64.b64encode(content).decode("utf-8")

            return {
                "status_code": status.HTTP_200_OK,
                "message": "File content retrieved successfully",
                "data": {
                    "project_id": project_id,
                    "file_path": normalized_path,
                    "name": full_path.name,
                    "format": "text" if text_content != "Binary file" else "binary",
                    "content": text_content,
                    "content_base64": content_base64,
                    "extension": file_extension,
                },
            }

        except ValueError as e:
            logger.error(f"Value Error: {str(e)}")
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

    @staticmethod
    async def search_project_files(project_id: str, query: str) -> Dict[str, Any]:
        """
        Search across files in the project for a specific query.

        Args:
            project_id: The slug of the project
            query: The search query

        Returns:
            Dict containing the search results

        Raises:
            ValueError: If the project is not found
            Exception: For any other errors
        """
        try:
            # Get project directory
            repo_url = get_repo_url(project_id)
            project_dir = get_project_dir_from_repo_url(repo_url)

            if not project_dir.exists():
                return error_response(
                    status_code=status.HTTP_404_NOT_FOUND,
                    message=f"Project {project_id} not found",
                    detail="The project directory does not exist",
                )

            if not query:
                return error_response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="Search query is required",
                    detail="Please provide a search query",
                )

            # Find files containing the query
            search_results = []
            await ProjectStructureService._search_files(
                project_dir, query, search_results, project_dir
            )

            return {
                "status_code": status.HTTP_200_OK,
                "message": "Search completed successfully",
                "data": {
                    "project_id": project_id,
                    "query": query,
                    "results": search_results,
                },
            }

        except ValueError as e:
            logger.error(f"Value Error: {str(e)}")
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

    @staticmethod
    async def _search_files(
        directory_path: Path,
        query: str,
        results: List[Dict[str, Any]],
        project_root: Path,
    ) -> None:
        """
        Recursively search files for the query.

        Args:
            directory_path: Path to the directory
            query: Search query
            results: List to store search results
            project_root: Root path of the project for relative paths
        """
        try:
            for item in directory_path.iterdir():
                # Skip __pycache__ directories, .git directory, and binary files
                if "__pycache__" in str(item) or ".git" in str(item):
                    continue

                if item.is_dir():
                    # Recursively search subdirectories
                    await ProjectStructureService._search_files(
                        item, query, results, project_root
                    )
                else:
                    # Skip binary files
                    if item.suffix.lower() in [
                        ".png",
                        ".jpg",
                        ".jpeg",
                        ".gif",
                        ".pdf",
                        ".zip",
                        ".pyc",
                    ]:
                        continue

                    # Try to read and search the file
                    try:
                        with open(item, "r", encoding="utf-8") as f:
                            content = f.read()

                        # Check if query is in content
                        if query.lower() in content.lower():
                            # Extract lines containing the query along with line numbers
                            matches = []
                            lines = content.split("\n")
                            for i, line in enumerate(lines):
                                if query.lower() in line.lower():
                                    # Get context (lines before and after the match)
                                    context_start = max(0, i - 2)
                                    context_end = min(len(lines), i + 3)
                                    context_lines = lines[context_start:context_end]

                                    matches.append(
                                        {
                                            "line_number": i + 1,  # 1-based line number
                                            "line": line.strip(),
                                            "context": "\n".join(context_lines),
                                        }
                                    )

                            # Add file to results
                            results.append(
                                {
                                    "name": item.name,
                                    "path": str(item.relative_to(project_root)),
                                    "full_path": str(item),
                                    "matches": matches,
                                    "match_count": len(matches),
                                }
                            )

                    except UnicodeDecodeError:
                        # Skip binary files that couldn't be decoded
                        continue
                    except Exception as e:
                        logger.warning(f"Error searching file {item}: {str(e)}")
                        continue

            # Sort results by number of matches (descending)
            results.sort(key=lambda x: x["match_count"], reverse=True)

        except Exception as e:
            logger.error(f"Error searching in {directory_path}: {str(e)}")
