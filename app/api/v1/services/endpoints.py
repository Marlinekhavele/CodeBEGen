import base64
import hashlib
import logging
import os
from typing import Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.db.database import get_db
from app.api.v1.models.endpoints import EndPoint
from app.api.v1.models.projects import Project
from app.api.v1.schemas.endpoints import EndpointFileRequest, EndpointFileResponse
from app.api.v1.utils.endpoint_services import (
    get_latest_commit_hash,
    get_project_dir_from_repo_url,
    resolve_file_path,
)
from app.api.v1.utils.git_operations import run_git_command
from app.api.v1.utils.git_utils import get_repo_url

logger = logging.getLogger(__name__)


class EndpointService:
    @staticmethod
    async def get_file(
        request: EndpointFileRequest, db: Session = Depends(get_db)
    ) -> EndpointFileResponse:
        """
        Retrieve a file based on the provided request and database session.

        Args:
            request (EditorFileRequest): The request containing file details.
            db (Session): The database session dependency.

        Returns:
            EditorFileResponse: The response containing file details or an error message.
        """
        repo_url = get_repo_url(request.project_id)
        logger.info(
            f"GET FILE: Retrieving file for endpoint {request.endpoint_path} from repo {repo_url}"
        )

        # Get the project by slug to get its UUID
        project = db.query(Project).filter(Project.slug == request.project_id).first()
        if not project:
            logger.error(
                f"GET FILE: Project with slug {request.project_id} not found in database"
            )
            raise ValueError(f"Project with ID {request.project_id} not found")

        project_uuid = project.id

        # Query the endpoint with the correct project UUID
        endpoint = (
            db.query(EndPoint)
            .filter(
                EndPoint.project_id == project_uuid,
                EndPoint.path == request.endpoint_path,
                EndPoint.method == request.method,
            )
            .first()
        )

        # Get description from database, ignore request description
        description = endpoint.description if endpoint else None
        logger.info(
            f"GET FILE: Found endpoint in database: {endpoint is not None}, description: {description}"
        )

        # Rest of the method remains the same...

        commit_hash = None
        try:
            project_dir = get_project_dir_from_repo_url(repo_url)
            logger.info(f"GET FILE: Found project directory at {project_dir}")
            commit_hash = get_latest_commit_hash(project_dir)
            file_path = resolve_file_path(
                project_dir, request.endpoint_path, request.method
            )
            logger.info(f"GET FILE: Resolved file path to {file_path}")

            if not file_path.exists():
                logger.warning(f"GET FILE: File not found at {file_path}")
                return EndpointFileResponse(
                    project_id=request.project_id,
                    endpoint_path=request.endpoint_path,
                    file_path=str(file_path.relative_to(project_dir)),
                    content_base64=None,
                    commit_hash=commit_hash,
                    method=request.method,  # Include the method from the request
                    message=f"File not found for endpoint: {request.endpoint_path}",
                    description=description,
                )

            logger.info(f"GET FILE: Reading file content from {file_path}")
            method = request.method
            with open(file_path, "r") as f:
                content = f.read()

            # Try to determine HTTP method from the file content
            detected_method = EndpointService._extract_method_from_content(content)
            # Use the detected method if available, otherwise fall back to the request method
            method = detected_method if detected_method else request.method
            logger.info(f"GET FILE: Using HTTP method: {method}")

            # Encode content as base64
            content_base64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
            logger.info(
                f"GET FILE: Successfully encoded file content as base64 ({len(content)} bytes)"
            )

            return EndpointFileResponse(
                project_id=request.project_id,
                endpoint_path=request.endpoint_path,
                file_path=str(file_path.relative_to(project_dir)),
                content_base64=content_base64,
                method=method,
                commit_hash=commit_hash,
                message="File retrieved successfully",
                description=description,
            )
        except ValueError as e:
            logger.error(f"Invalid repository or project: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error retrieving file: {str(e)}")
            raise

    @staticmethod
    async def create_endpoint(
        request: EndpointFileRequest, db: Session = Depends(get_db)
    ) -> EndpointFileResponse:
        """
        Create a new endpoint based on the provided request and database session.

        Args:
            request (EditorFileRequest): The request containing endpoint details.
            db (Session): The database session dependency.

        Returns:
            EditorFileResponse: The response containing the created endpoint details.
        """
        repo_url = get_repo_url(request.project_id)
        logger.info(
            f"CREATE FILE: Creating new file for endpoint {request.endpoint_path} in repo {repo_url}"
        )
        try:
            project_dir = get_project_dir_from_repo_url(repo_url)
            logger.info(f"CREATE FILE: Found project directory at {project_dir}")

            file_path = resolve_file_path(
                project_dir, request.endpoint_path, request.method
            )
            logger.info(f"CREATE FILE: Resolved file path to {file_path}")

            if file_path.exists():
                logger.warning(f"CREATE FILE: File already exists at {file_path}")
                return EndpointFileResponse(
                    project_id=request.project_id,
                    endpoint_path=request.endpoint_path,
                    file_path=str(file_path.relative_to(project_dir)),
                    content_base64=None,
                    method=request.method,  # Include the method from the request
                    message=f"File already exists for endpoint: {request.endpoint_path}",
                    description=request.description,
                )

            # Ensure directory exists
            logger.info(
                f"CREATE FILE: Ensuring parent directory exists at {file_path.parent}"
            )
            os.makedirs(file_path.parent, exist_ok=True)

            # Decode base64 content
            content = ""
            if request.content_base64:
                try:
                    content = base64.b64decode(request.content_base64).decode("utf-8")
                    logger.info(
                        f"CREATE FILE: Decoded {len(request.content_base64)} bytes of base64 content"
                    )
                except Exception as e:
                    logger.error(
                        f"CREATE FILE: Failed to decode base64 content: {str(e)}"
                    )

            # Extract method from content if not provided
            method = request.method
            if not method and content:
                method = EndpointService._extract_method_from_content(content)
                logger.info(f"CREATE FILE: Detected HTTP method from content: {method}")

            # Write content to file
            logger.info(f"CREATE FILE: Writing {len(content)} bytes to {file_path}")
            with open(file_path, "w") as f:
                f.write(content)

            commit_hash = None
            # Commit the new file to Git
            try:
                logger.info(f"CREATE FILE: Adding file to Git index: {file_path}")
                run_git_command(
                    ["git", "add", str(file_path.relative_to(project_dir))],
                    cwd=project_dir,
                )

                # Include method in commit message if available
                commit_message = (
                    f"feat: Add {method} endpoint {request.endpoint_path}"
                    if method
                    else f"feat: Add endpoint {request.endpoint_path}"
                )
                logger.info(
                    f"CREATE FILE: Committing file to Git repository with message: {commit_message}"
                )
                run_git_command(
                    ["git", "commit", "-m", commit_message], cwd=project_dir
                )

                # Get the commit hash
                logger.info("CREATE FILE: Getting commit hash")
                commit_hash = get_latest_commit_hash(project_dir)
                logger.info(f"CREATE FILE: Commit hash: {commit_hash}")

                # Push changes
                logger.info("CREATE FILE: Pushing changes to remote repository")
                push_result = run_git_command(["git", "push"], cwd=project_dir)
                logger.info(f"CREATE FILE: Push result: {push_result}")

                # After successful Git operations, save endpoint to database
                if db:
                    try:
                        logger.info("CREATE FILE: Saving endpoint to database")

                        # Get the project by slug to get its UUID
                        project = (
                            db.query(Project)
                            .filter(Project.slug == request.project_id)
                            .first()
                        )

                        if not project:
                            logger.error(
                                f"CREATE FILE: Project with slug {request.project_id} not found in database"
                            )
                        else:
                            # Use the project's UUID as the project_id for the endpoint
                            project_uuid = project.id
                            logger.info(
                                f"CREATE FILE: Found project UUID: {project_uuid} for slug: {request.project_id}"
                            )

                            # Create new endpoint record with the project UUID
                            new_endpoint = EndPoint(
                                path=request.endpoint_path,  # Changed from name to path
                                method=(
                                    method if method else "UNKNOWN"
                                ),  # Changed from http_method to method
                                project_id=project_uuid,  # Use UUID here, not slug
                                description=request.description,
                                file_hash=hashlib.md5(
                                    content.encode()
                                ).hexdigest(),  # Add file_hash
                            )
                            # Add to database
                            db.add(new_endpoint)
                            db.commit()
                            logger.info(
                                f"CREATE FILE: Successfully saved endpoint to database with project_id: {project_uuid}"
                            )
                    except Exception as db_error:
                        logger.error(
                            f"CREATE FILE: Database operation failed: {str(db_error)}"
                        )
                        # Rollback in case of error
                        db.rollback()
                        # We don't fail the operation if DB fails, just log it
            except Exception as e:
                logger.error(f"CREATE FILE: Git operation failed: {str(e)}")
                # We don't fail the operation if Git fails, just log it

            logger.info(
                f"CREATE FILE: Successfully created file for endpoint {request.endpoint_path}"
            )
            return EndpointFileResponse(
                project_id=request.project_id,
                endpoint_path=request.endpoint_path,
                file_path=str(file_path.relative_to(project_dir)),
                content_base64=request.content_base64,
                commit_hash=commit_hash,
                method=method,
                message="File created successfully",
                description=request.description,
            )
        except ValueError as e:
            logger.error(f"Invalid repository or project: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error creating file: {str(e)}")
            raise

    @staticmethod
    async def update_file(request: EndpointFileRequest) -> EndpointFileResponse:
        """
        Update an existing file based on the provided request.

        Args:
            request (EditorFileRequest): The request containing updated file details.

        Returns:
            EditorFileResponse: The response containing the updated file details.
        """
        repo_url = get_repo_url(request.project_id)
        logger.info(
            f"UPDATE FILE: Updating file for endpoint {request.endpoint_path} in repo {repo_url}"
        )
        try:
            project_dir = get_project_dir_from_repo_url(repo_url)
            current_commit_hash = get_latest_commit_hash(project_dir)
            logger.info(f"UPDATE FILE: Found project directory at {project_dir}")

            file_path = resolve_file_path(
                project_dir, request.endpoint_path, request.method
            )
            logger.info(f"UPDATE FILE: Resolved file path to {file_path}")

            if not file_path.exists():
                logger.warning(f"UPDATE FILE: File not found at {file_path}")
                return EndpointFileResponse(
                    project_id=request.project_id,
                    endpoint_path=request.endpoint_path,
                    file_path=str(file_path.relative_to(project_dir)),
                    content_base64=None,
                    commit_hash=current_commit_hash,
                    message=f"File not found for endpoint: {request.endpoint_path}",
                    description=request.description,
                )

            # Decode base64 content
            content = ""
            if request.content_base64:
                try:
                    content = base64.b64decode(request.content_base64).decode("utf-8")
                    logger.info(
                        f"UPDATE FILE: Decoded {len(request.content_base64)} bytes of base64 content"
                    )
                except Exception as e:
                    logger.error(
                        f"UPDATE FILE: Failed to decode base64 content: {str(e)}"
                    )

            # Extract method from content if not provided
            method = request.method
            if not method and content:
                method = EndpointService._extract_method_from_content(content)
                logger.info(f"UPDATE FILE: Detected HTTP method from content: {method}")

            # Write content to file
            logger.info(f"UPDATE FILE: Writing {len(content)} bytes to {file_path}")
            with open(file_path, "w") as f:
                f.write(content)

            commit_hash = None
            # Commit the updated file to Git
            try:
                logger.info(f"UPDATE FILE: Adding file to Git index: {file_path}")
                run_git_command(
                    ["git", "add", str(file_path.relative_to(project_dir))],
                    cwd=project_dir,
                )

                # Include method in commit message if available
                commit_message = (
                    f"feat: Update {method} endpoint {request.endpoint_path}"
                    if method
                    else f"feat: Update endpoint {request.endpoint_path}"
                )
                logger.info(
                    f"UPDATE FILE: Committing file to Git repository with message: {commit_message}"
                )
                run_git_command(
                    [
                        "git",
                        "commit",
                        "-m",
                        f"feat: Update endpoint {request.endpoint_path}",
                    ],
                    cwd=project_dir,
                )

                # Get the commit hash
                logger.info("UPDATE FILE: Getting commit hash")
                commit_hash = get_latest_commit_hash(project_dir)
                logger.info(f"UPDATE FILE: Commit hash: {commit_hash}")

                # Push changes
                logger.info("UPDATE FILE: Pushing changes to remote repository")
                push_result = run_git_command(["git", "push"], cwd=project_dir)
                logger.info(f"UPDATE FILE: Push result: {push_result}")
            except Exception as e:
                logger.error(f"UPDATE FILE: Git operation failed: {str(e)}")
                # We don't fail the operation if Git fails, just log it

            logger.info(
                f"UPDATE FILE: Successfully updated file for endpoint {request.endpoint_path}"
            )
            return EndpointFileResponse(
                project_id=request.project_id,
                endpoint_path=request.endpoint_path,
                file_path=str(file_path.relative_to(project_dir)),
                content_base64=request.content_base64,
                commit_hash=commit_hash,  # Changed from current_commit_hash to commit_hash
                method=method,
                message="File updated successfully",
                description=request.description,
            )
        except ValueError as e:
            logger.error(f"Invalid repository or project: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error updating file: {str(e)}")
            raise

    """ Enhanced delete_file method with improved security, error handling, and audit logging """

    @staticmethod
    async def delete_file(
        request: EndpointFileRequest, db: Session = None
    ) -> EndpointFileResponse:
        """
        Delete a file based on the provided request with enhanced security and error handling.

        Args:
            request (EditorFileRequest): The request containing file details to delete.
            db (Session, optional): The database session dependency. Defaults to None.

        Returns:
            EditorFileResponse: The response confirming the deletion or an error message.
        """
        repo_url = get_repo_url(request.project_id)
        logger.info(
            f"DELETE FILE: Deleting file for endpoint {request.endpoint_path} with method {request.method} in repo {repo_url}"
        )

        # Check if this is a critical system endpoint
        if EndpointService.is_critical_endpoint(request.endpoint_path):
            logger.warning(
                f"DELETE FILE: Attempt to delete critical endpoint {request.endpoint_path}"
            )
            raise ValueError("Cannot delete critical system endpoint")

        # Start a transaction to ensure database consistency
        # We'll use a try/except block to properly handle rollbacks
        transaction = None
        if db:
            transaction = db.begin_nested()

        try:
            project_dir = get_project_dir_from_repo_url(repo_url)
            logger.info(f"DELETE FILE: Found project directory at {project_dir}")

            file_path = resolve_file_path(
                project_dir, request.endpoint_path, request.method
            )
            logger.info(f"DELETE FILE: Resolved file path to {file_path}")

            # Store relative path for return value regardless of file existence
            relative_path = (
                str(file_path.relative_to(project_dir)) if file_path.exists() else None
            )

            # Check if endpoint exists in database before attempting deletion
            endpoint_id = None
            if db:
                try:
                    # Get the project by slug to get its UUID
                    project = (
                        db.query(Project)
                        .filter(Project.slug == request.project_id)
                        .first()
                    )

                    if not project:
                        logger.error(
                            f"DELETE FILE: Project with slug {request.project_id} not found in database"
                        )
                        if transaction:
                            transaction.rollback()
                        raise ValueError(
                            f"Project with ID {request.project_id} not found"
                        )

                    # Store project_uuid for later use
                    project_uuid = project.id

                    # Find the endpoint record - we'll need this information regardless of file existence
                    endpoint = (
                        db.query(EndPoint)
                        .filter(
                            EndPoint.path == request.endpoint_path,
                            EndPoint.method == request.method,
                            EndPoint.project_id == project_uuid,
                        )
                        .first()
                    )

                    if endpoint:
                        endpoint_id = endpoint.id

                    # If neither file nor database entry exists, we should abort
                    if not file_path.exists() and not endpoint:
                        logger.warning(
                            f"DELETE FILE: Neither file nor database entry exists for {request.endpoint_path}"
                        )
                        if transaction:
                            transaction.rollback()
                        return EndpointFileResponse(
                            project_id=request.project_id,
                            endpoint_path=request.endpoint_path,
                            file_path=relative_path,
                            content_base64=None,
                            method=request.method,
                            message=f"Endpoint not found: {request.endpoint_path}",
                            description=request.description,
                        )

                except Exception as db_error:
                    logger.error(
                        f"DELETE FILE: Database lookup failed: {str(db_error)}"
                    )
                    if transaction:
                        transaction.rollback()
                    raise ValueError(f"Database error: {str(db_error)}")

            # Use the method from the request
            method = request.method

            # Delete the file if it exists
            if file_path.exists():
                logger.info(f"DELETE FILE: Removing file at {file_path}")
                os.remove(file_path)
            else:
                logger.warning(f"DELETE FILE: File not found at {file_path}")
                # Continue with database deletion if endpoint exists

            # Delete the database entry if db is provided and endpoint exists
            if db and endpoint_id:
                try:
                    logger.info(
                        f"DELETE FILE: Processing endpoint {endpoint_id} deletion in database"
                    )

                    # Determine if we should use soft or hard delete
                    # Using the settings module for configuration
                    from config import settings

                    use_soft_delete = getattr(settings, "USE_SOFT_DELETE", True)

                    # Delete the endpoint record we found earlier
                    if endpoint:
                        if use_soft_delete and hasattr(endpoint, "deleted_at"):
                            # Soft delete - set the deleted_at timestamp
                            from datetime import datetime

                            endpoint.deleted_at = datetime.utcnow()
                            endpoint.is_deleted = True  # If you have this field
                            db.add(endpoint)  # Update the record
                            logger.info(
                                "DELETE FILE: Endpoint soft-deleted (marked as deleted)"
                            )
                        else:
                            # Hard delete - permanently remove from database
                            db.delete(endpoint)
                            logger.info(
                                "DELETE FILE: Endpoint hard-deleted from database"
                            )
                    else:
                        logger.warning("DELETE FILE: Endpoint not found in database")

                except Exception as db_error:
                    logger.error(
                        f"DELETE FILE: Database deletion failed: {str(db_error)}"
                    )
                    if transaction:
                        transaction.rollback()
                    raise ValueError(f"Database error: {str(db_error)}")

            commit_hash = None
            # Commit the deletion to Git - only if file existed
            if file_path.exists() or relative_path:
                try:
                    logger.info("DELETE FILE: Adding file deletion to Git index")
                    run_git_command(
                        ["git", "add", relative_path],
                        cwd=project_dir,
                    )

                    # Include method in commit message
                    commit_message = (
                        f"feat: Delete {method} endpoint {request.endpoint_path}"
                    )
                    logger.info(
                        f"DELETE FILE: Committing file deletion with message: {commit_message}"
                    )
                    run_git_command(
                        ["git", "commit", "-m", commit_message],
                        cwd=project_dir,
                    )

                    # Get the commit hash
                    logger.info("DELETE FILE: Getting commit hash")
                    commit_hash = get_latest_commit_hash(project_dir)
                    logger.info(f"DELETE FILE: Commit hash: {commit_hash}")

                    # Push changes
                    logger.info("DELETE FILE: Pushing changes to remote repository")
                    push_result = run_git_command(["git", "push"], cwd=project_dir)
                    logger.info(f"DELETE FILE: Push result: {push_result}")
                except Exception as git_err:
                    logger.error(f"DELETE FILE: Git operation failed: {str(git_err)}")

            # Commit the transaction if everything succeeded
            if transaction:
                transaction.commit()
                db.commit()
                logger.info("DELETE FILE: Database transaction committed successfully")

            logger.info(
                f"DELETE FILE: Successfully deleted endpoint {request.endpoint_path}"
            )
            return EndpointFileResponse(
                project_id=request.project_id,
                endpoint_path=request.endpoint_path,
                file_path=relative_path,
                commit_hash=commit_hash,
                content_base64=None,
                method=method,
                endpoint_id=endpoint_id,
                message="Endpoint deleted successfully",
                description=request.description,
            )

        except ValueError as ve:
            # For expected errors, pass them through
            if transaction:
                transaction.rollback()
            logger.error(f"DELETE FILE: Validation error: {str(ve)}")
            raise
        except Exception as e:
            # For unexpected errors, provide a generic message
            if transaction:
                transaction.rollback()
            logger.error(f"DELETE FILE: Error deleting file: {str(e)}")
            raise ValueError(f"Failed to delete endpoint: {str(e)}")

    @staticmethod
    def is_critical_endpoint(endpoint_path: str) -> bool:
        """
        Check if an endpoint is critical to system operation and shouldn't be deleted.

        Args:
            endpoint_path (str): The path of the endpoint to check

        Returns:
            bool: True if the endpoint is critical, False otherwise
        """
        # List of critical endpoint patterns
        CRITICAL_PATTERNS = [
            "/api/v1/auth",
            "/api/v1/admin",
            "/health",
            "/api/v1/system",
        ]

        return any(endpoint_path.startswith(pattern) for pattern in CRITICAL_PATTERNS)

    @staticmethod
    def _extract_method_from_content(content: str) -> Optional[str]:
        """
        Extract the HTTP method from the provided file content.

        Args:
            content (str): The content of the file.

        Returns:
            Optional[str]: The extracted HTTP method, or None if not found.
        """
        if not content:
            return None

        # Common patterns for FastAPI route decorators
        method_patterns = [
            r"@router\.get\s*\(",
            r"@router\.post\s*\(",
            r"@router\.put\s*\(",
            r"@router\.delete\s*\(",
            r"@router\.patch\s*\(",
            r"@app\.get\s*\(",
            r"@app\.post\s*\(",
            r"@app\.put\s*\(",
            r"@app\.delete\s*\(",
            r"@app\.patch\s*\(",
        ]

        import re

        for pattern in method_patterns:
            match = re.search(pattern, content)
            if match:
                # Extract the method from the pattern (e.g., 'get' from '@router.get')
                method = match.group(0).split(".")[1].split("(")[0].strip().upper()
                return method
        return None
