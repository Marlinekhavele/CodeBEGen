import logging
import os

from app.api.v1.utils.endpoint_services import (
    get_project_dir_from_repo_url,
    resolve_file_path,
)
from app.api.v1.utils.git_operations import run_git_command
from app.api.v1.utils.git_utils import get_repo_url

logger = logging.getLogger(__name__)


# Define custom exceptions
class DuplicateEndpointError(Exception):
    """Raised when attempting to commit an endpoint that already exists."""

    pass


class GitService:
    @staticmethod
    async def commit_code_update(
        project_id: str, new_code: str, endpoint_path: str = None, method: str = None
    ) -> str:
        """
        Commit updated code to the project repository and return the new commit hash.

        Parameters:
        project_id (str): The project ID (slug)
        new_code (str): The new code content to be written to the file.
        endpoint_path (str, optional): The endpoint path (e.g., 'api/v1/users')
        method (str, optional): The HTTP method (GET, POST, PUT, DELETE)

        Returns:
        str: The new commit hash after the changes have been committed.

        Raises:
        ValueError: If the project directory does not exist.
        subprocess.CalledProcessError: If any git command fails.
        """
        try:
            # Get the repository URL for the project
            repo_url = get_repo_url(project_id)
            logger.info(
                f"Committing code update for project {project_id} with repo URL: {repo_url}"
            )

            # Get the project directory
            project_dir = get_project_dir_from_repo_url(repo_url)
            logger.info(f"Found project directory at {project_dir}")

            # Determine the file path
            if endpoint_path and method:

                file_path = resolve_file_path(project_dir, endpoint_path, method)
                logger.info(f"Resolved file path to {file_path}")
            else:
                # Default to a temporary file if endpoint path and method are not provided
                file_path = project_dir / "endpoints" / "temp_generated_code.py"
                logger.info(f"Using temporary file path: {file_path}")

                # Create the endpoints directory if it doesn't exist
                os.makedirs(file_path.parent, exist_ok=True)

            # Write the new code to the specified file
            logger.info(f"Writing {len(new_code)} bytes to {file_path}")
            with open(file_path, "w") as file:
                file.write(new_code)

            # Stage the changes for the specified file
            logger.info(f"Adding file to Git index: {file_path}")
            run_git_command(
                ["git", "add", str(file_path.relative_to(project_dir))], cwd=project_dir
            )

            # Commit the changes
            commit_message = f'Update code in "{file_path.relative_to(project_dir)}"'
            logger.info(
                f"Committing file to Git repository with message: {commit_message}"
            )
            run_git_command(["git", "commit", "-m", commit_message], cwd=project_dir)

            # Get the new commit hash
            logger.info("Getting commit hash")
            commit_hash = run_git_command(["git", "rev-parse", "HEAD"], cwd=project_dir)
            logger.info(f"Commit hash: {commit_hash}")

            # Push changes
            logger.info("Pushing changes to remote repository")
            push_result = run_git_command(["git", "push"], cwd=project_dir)
            logger.info(f"Push result: {push_result}")

            return commit_hash

        except Exception as e:
            logger.error(f"Git operation failed: {str(e)}")
            raise e

    @staticmethod
    async def commit_file_update(
        project_id: str, new_code: str, file_path: str, commit_message: str = None
    ) -> str:
        """
        Commit any file to the project repository and return the new commit hash.

        Parameters:
        project_id (str): The project ID (slug)
        new_code (str): The new code content to be written to the file.
        file_path (str): The relative path to the file within the project
        commit_message (str, optional): Custom commit message. If not provided, a default one will be used.

        Returns:
        str: The new commit hash after the changes have been committed.

        Raises:
        ValueError: If the project directory does not exist.
        subprocess.CalledProcessError: If any git command fails.
        """
        try:
            # Get the repository URL for the project
            repo_url = get_repo_url(project_id)
            logger.info(
                f"Committing file update for project {project_id} with repo URL: {repo_url}"
            )

            # Get the project directory
            project_dir = get_project_dir_from_repo_url(repo_url)
            logger.info(f"Found project directory at {project_dir}")

            # Normalize the file path and handle both absolute and relative paths
            file_path = file_path.replace("\\", "/")  # Normalize slashes
            if os.path.isabs(file_path):
                # If absolute path, make it relative to project_dir
                try:
                    file_path = os.path.relpath(file_path, project_dir)
                except ValueError:
                    # If relpath fails, just use the filename
                    file_path = os.path.basename(file_path)

            # Determine full file path
            full_file_path = os.path.join(project_dir, file_path)
            logger.info(f"Full file path: {full_file_path}")

            # Create directory structure if it doesn't exist
            directory = os.path.dirname(full_file_path)
            if directory and not os.path.exists(directory):
                logger.info(f"Creating directory: {directory}")
                os.makedirs(directory, exist_ok=True)

            # Write the new code to the specified file
            logger.info(f"Writing {len(new_code)} bytes to {full_file_path}")
            with open(full_file_path, "w", encoding="utf-8") as file:
                file.write(new_code)

            # Stage the changes for the specified file
            logger.info(f"Adding file to Git index: {file_path}")
            run_git_command(["git", "add", file_path], cwd=project_dir)

            # Prepare commit message
            if not commit_message:
                commit_message = f'Add/update "{file_path}"'
            logger.info(
                f"Committing file to Git repository with message: {commit_message}"
            )

            # Commit the changes with specific git config
            run_git_command(
                ["git", "config", "user.name", "CodeBEGen Bot"], cwd=project_dir
            )
            run_git_command(
                ["git", "config", "user.email", "codebegen@example.com"],
                cwd=project_dir,
            )
            run_git_command(["git", "commit", "-m", commit_message], cwd=project_dir)

            # Get the new commit hash
            logger.info("Getting commit hash")
            commit_hash = run_git_command(["git", "rev-parse", "HEAD"], cwd=project_dir)
            logger.info(f"Commit hash: {commit_hash}")

            # Push changes
            logger.info("Pushing changes to remote repository")
            push_result = run_git_command(["git", "push"], cwd=project_dir)
            logger.info(f"Push result: {push_result}")

            return commit_hash

        except Exception as e:
            logger.error(f"Git file operation failed: {str(e)}")
            raise e

    @staticmethod
    async def commit_binary_file_update(
        project_id: str,
        binary_content: bytes,
        file_path: str,
        commit_message: str = None,
    ) -> str:
        """
        Commit a binary file to the project repository and return the new commit hash.

        Parameters:
        project_id (str): The project ID (slug)
        binary_content (bytes): The binary content to be written to the file
        file_path (str): The relative path to the file within the project
        commit_message (str, optional): Custom commit message. If not provided, a default one will be used.

        Returns:
        str: The new commit hash after the changes have been committed.

        Raises:
        ValueError: If the project directory does not exist.
        subprocess.CalledProcessError: If any git command fails.
        """
        try:
            # Get the repository URL for the project
            repo_url = get_repo_url(project_id)
            logger.info(
                f"Committing binary file update for project {project_id} with repo URL: {repo_url}"
            )

            # Get the project directory
            project_dir = get_project_dir_from_repo_url(repo_url)
            logger.info(f"Found project directory at {project_dir}")

            # Normalize the file path and handle both absolute and relative paths
            file_path = file_path.replace("\\", "/")  # Normalize slashes
            if os.path.isabs(file_path):
                # If absolute path, make it relative to project_dir
                try:
                    file_path = os.path.relpath(file_path, project_dir)
                except ValueError:
                    # If relpath fails, just use the filename
                    file_path = os.path.basename(file_path)

            # Determine full file path
            full_file_path = os.path.join(project_dir, file_path)
            logger.info(f"Full file path: {full_file_path}")

            # Create directory structure if it doesn't exist
            directory = os.path.dirname(full_file_path)
            if directory and not os.path.exists(directory):
                logger.info(f"Creating directory: {directory}")
                os.makedirs(directory, exist_ok=True)

            # Write the binary content to the specified file
            logger.info(f"Writing {len(binary_content)} bytes to {full_file_path}")
            with open(full_file_path, "wb") as file:
                file.write(binary_content)

            # Stage the changes for the specified file
            logger.info(f"Adding file to Git index: {file_path}")
            run_git_command(["git", "add", file_path], cwd=project_dir)

            # Prepare commit message
            if not commit_message:
                commit_message = f'Add/update binary file "{file_path}"'
            logger.info(
                f"Committing binary file to Git repository with message: {commit_message}"
            )

            # Commit the changes with specific git config
            run_git_command(
                ["git", "config", "user.name", "CodeBEGen Bot"], cwd=project_dir
            )
            run_git_command(
                ["git", "config", "user.email", "codebegen@example.com"],
                cwd=project_dir,
            )
            run_git_command(["git", "commit", "-m", commit_message], cwd=project_dir)

            # Get the new commit hash
            logger.info("Getting commit hash")
            commit_hash = run_git_command(["git", "rev-parse", "HEAD"], cwd=project_dir)
            logger.info(f"Commit hash: {commit_hash}")

            # Push changes
            logger.info("Pushing changes to remote repository")
            push_result = run_git_command(["git", "push"], cwd=project_dir)
            logger.info(f"Push result: {push_result}")

            return commit_hash

        except Exception as e:
            logger.error(f"Git binary file operation failed: {str(e)}")
            raise e
