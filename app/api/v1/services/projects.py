import hashlib
import logging
import os
import random
import shutil
import string
import tempfile
import zipfile
from pathlib import Path

import httpx
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.db.database import get_db
from app.api.v1.models.endpoints import EndPoint
from app.api.v1.models.projects import Project
from app.api.v1.schemas.projects import ProjectInitRequest, ProjectInitResponse
from app.api.v1.utils.get_default_download_directory import (
    get_default_download_directory,
)
from app.api.v1.utils.git_operations import (
    REPOS_DIR,
    clone_template_repo,
    configure_git_for_project,
    create_project_directory,
    ensure_repos_directory,
    push_to_remote,
    update_git_remote,
)
from app.api.v1.utils.git_utils import create_gitea_repo
from config import BASE_DIR, settings

logger = logging.getLogger(__name__)


class ProjectInitService:
    @staticmethod
    def add_default_endpoints(project_id: str, db: Session = Depends(get_db)) -> None:
        """
        Add default login and signup endpoints to the database for a new project

        Args:
            project_id: The ID (UUID) of the newly created project
            db: Database session
        """
        logger.info(f"Starting add_default_endpoints for project_id: {project_id}")
        try:
            # Define default endpoints with simpler paths
            default_endpoints = [
                {
                    "path": "login",
                    "method": "POST",
                    "description": "Default login endpoint",
                },
                {
                    "path": "signup",
                    "method": "POST",
                    "description": "Default signup endpoint",
                },
            ]

            logger.info(f"Adding {len(default_endpoints)} default endpoints")

            # Add each default endpoint to the database
            for endpoint_data in default_endpoints:
                # Check if endpoint already exists
                existing_endpoint = (
                    db.query(EndPoint)
                    .filter(
                        EndPoint.path == endpoint_data["path"],
                        EndPoint.method == endpoint_data["method"],
                        EndPoint.project_id == project_id,
                    )
                    .first()
                )

                if existing_endpoint:
                    logger.info(
                        f"Endpoint already exists: {endpoint_data['path']} {endpoint_data['method']}"
                    )
                    continue

                logger.info(
                    f"Creating endpoint: {endpoint_data['path']} {endpoint_data['method']}"
                )
                endpoint = EndPoint(
                    path=endpoint_data["path"],
                    method=endpoint_data["method"],
                    description=endpoint_data["description"],
                    project_id=project_id,
                    file_hash=hashlib.md5(
                        endpoint_data["path"].encode()
                    ).hexdigest(),  # Add file_hash
                )
                db.add(endpoint)
                logger.info(f"Added endpoint to session: {endpoint_data['path']}")

            # Commit the changes
            logger.info("Committing endpoints to database")
            db.commit()
            logger.info(
                f"Successfully added default endpoints for project {project_id}"
            )
        except Exception as e:
            logger.error(f"Error adding default endpoints: {str(e)}", exc_info=True)
            db.rollback()

    @staticmethod
    async def initialize_project(
        init_request: ProjectInitRequest, db: Session = Depends(get_db)
    ) -> ProjectInitResponse:
        """
        Initialize a new project with a unique slug and repository setup.

        Args:
            init_request (InitRequest): Object containing project initialization details,
                                    including project_name
            db (Session, optional): SQLAlchemy database session. Defaults to None.
                                If provided, a project record will be created in the database.

        Returns:
            InitResponse: Object containing:
                - project_id: The generated project slug
                - project_url: A formatted URL for accessing the project
        """
        # Generate a slug from the project name
        # Convert to lowercase and replace spaces with dashes
        logger.info(f"BASE_DIR is: {Path(BASE_DIR).absolute()}")
        logger.info(f"Current working directory is: {Path.cwd().absolute()}")
        base_slug = init_request.project_name.lower().replace(" ", "-")

        # Generate a random 6-character alphanumeric string
        random_string = "".join(
            random.choices(string.ascii_lowercase + string.digits, k=6)
        )

        # Combine to create the final slug
        slug = f"{base_slug}-{random_string}"

        # Create a proper URL with the slug and base URL
        project_url = f"https://{slug}.{settings.CODE_BE_GEN_BASE_URL}"

        language = init_request.language
        framework = (
            init_request.framework
        )  # Create Gitea repository (if credentials are provided)
        repo_url = ""
        if settings.GITEA_TOKEN:
            try:
                repo_url = create_gitea_repo(slug)
                logger.info(f"Created Gitea repository: {repo_url}")

                # Ensure the repos directory exists
                ensure_repos_directory()

                # Create a directory for the project
                project_dir = create_project_directory(slug)

                # Clone the template repository
                clone_template_repo(project_dir, language)

                # Configure Git for the project
                configure_git_for_project(project_dir)

                # Update the git remote to point to the new repository
                update_git_remote(
                    project_dir, repo_url
                )  # Push the code to the new repository
                push_to_remote(project_dir)

                logger.info(
                    f"Successfully initialized project {slug} with repository {repo_url}"
                )
            except Exception as e:
                # Repository setup failed - this should be a hard failure
                error_msg = f"Failed to initialize project repository: {str(e)}"
                logger.error(error_msg)
                # Clean up the project directory since repository creation failed
                try:
                    import shutil

                    if "project_dir" in locals():
                        shutil.rmtree(project_dir)
                        logger.info(f"Cleaned up project directory: {project_dir}")
                except Exception as cleanup_error:
                    logger.warning(
                        f"Failed to clean up project directory: {cleanup_error}"
                    )
                raise Exception(error_msg)
        else:
            logger.warning("No Gitea token provided - skipping repository creation")

        # Create a proper URL with the slug and base URL
        project_url = f"https://{slug}.{settings.CODE_BE_GEN_BASE_URL}"

        # Create a Project record in the database if db is provided
        project_db_id = None

        if db:
            try:
                # Create a new project record without user_id
                project = Project(
                    name=init_request.project_name,
                    description=init_request.project_name,  # Using project name as description for now
                    slug=slug,
                    language="python",  # Default language
                    framework="fastapi",  # Default framework
                )

                # Add to session and flush to get the ID without committing yet
                db.add(project)
                db.flush()
                # Store the project's database ID
                project_db_id = project.id
                logger.info(f"Created project with database ID: {project_db_id}")

                # Now commit the transaction
                db.commit()
                logger.info(
                    f"Successfully committed project record to database with slug: {slug}"
                )

            except Exception as e:
                logger.error(f"Error creating project record: {str(e)}", exc_info=True)
                db.rollback()
                # If database operations fail but repository was created,
                # we should still raise an exception to indicate partial failure
                error_msg = f"Repository created successfully but database operations failed: {str(e)}"
                raise Exception(error_msg)
        else:
            logger.warning("Skipping database operations. No db provided.")

        # Add default endpoints if database session is provided
        if (
            db and project_db_id
        ):  # Only if we have both the db session and the project ID
            logger.info(
                f"Calling add_default_endpoints with project_db_id: {project_db_id}"
            )
            ProjectInitService.add_default_endpoints(project_db_id, db)
        else:
            logger.warning(
                f"Skipping add_default_endpoints. db provided: {db is not None}, project_db_id: {project_db_id}"
            )

        # Return the response with the generated slug as repo_url and the formatted project_url
        return ProjectInitResponse(
            project_id=slug,
            project_url=project_url,
            language=language,
            framework=framework,
        )

    @staticmethod
    async def download_project_gitea_repo(
        project_name: str,
        output_path: Path = None,
        use_default_download_dir: bool = False,
        save_as_zip: bool = True,
    ) -> Path:
        """
        Downloads a project from Gitea and saves it as a ZIP file.

        Args:
            project_name: Repository name
            output_path: Custom path to save the ZIP file or directory (optional)
            use_default_download_dir: Whether to use system's Downloads folder
            save_as_zip: Whether to save as ZIP (True) or extract (False)

        Returns:
            Path: Path to the downloaded ZIP file or extracted directory

        Raises:
            HTTPException: If download fails
        """
        try:
            # Construct the Gitea URL for downloading the repository
            download_url = f"{settings.GITEA_API_URL}/repos/{settings.GIT_OWNER}/{project_name}/archive/main.zip"

            logger.info(f"Attempting to download from: {download_url}")

            # Set up headers with token for authentication
            headers = {}
            if hasattr(settings, "GITEA_TOKEN") and settings.GITEA_TOKEN:
                headers["Authorization"] = f"token {settings.GITEA_TOKEN}"

            # Determine destination directory and filename
            if output_path:
                # Use provided output path
                if save_as_zip and output_path.suffix != ".zip":
                    # If saving as ZIP but path doesn't end with .zip, append filename
                    dest_dir = (
                        output_path if output_path.is_dir() else output_path.parent
                    )
                    dest_file = dest_dir / f"{project_name}.zip"
                else:
                    # Use provided path as is
                    dest_file = output_path
            else:
                # Use default directory
                if use_default_download_dir:
                    # Use system's Downloads folder
                    download_dir = get_default_download_directory()
                    dest_dir = download_dir
                else:
                    # Use project's repos directory
                    ensure_repos_directory()
                    dest_dir = REPOS_DIR

                # Create filename with ZIP extension if saving as ZIP
                if save_as_zip:
                    dest_file = dest_dir / f"{project_name}.zip"
                else:
                    dest_file = dest_dir / project_name

            # Create parent directory if it doesn't exist
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Will save to: {dest_file}")

            # Download the repository
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(download_url, headers=headers)

                if response.status_code != 200:
                    error_msg = f"Failed to download repository: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    raise HTTPException(
                        status_code=response.status_code, detail=error_msg
                    )

                if save_as_zip:
                    # Save directly as ZIP file
                    with open(dest_file, "wb") as f:
                        f.write(response.content)
                    logger.info(f"Successfully saved ZIP file to {dest_file}")
                    return dest_file
                else:
                    # Extract the ZIP content to a directory
                    # Create a temporary file first
                    with tempfile.NamedTemporaryFile(
                        suffix=".zip", delete=False
                    ) as temp_file:
                        temp_file_path = temp_file.name
                        temp_file.write(response.content)

                    # Create/clear destination directory
                    if dest_file.exists() and dest_file.is_dir():
                        # Clear existing directory
                        logger.info(f"Clearing existing directory at {dest_file}")
                        for item in dest_file.iterdir():
                            if item.is_dir():
                                shutil.rmtree(item)
                            else:
                                item.unlink()
                    elif not dest_file.exists():
                        dest_file.mkdir(parents=True, exist_ok=True)

                    # Extract the zip file
                    with zipfile.ZipFile(temp_file_path, "r") as zip_ref:
                        # Get the root directory in the zip (usually {project_name}-main/)
                        root_dirs = {
                            item.split("/")[0]
                            for item in zip_ref.namelist()
                            if "/" in item
                        }
                        root_dir = root_dirs.pop() if root_dirs else ""

                        # Extract all files
                        zip_ref.extractall(dest_file.parent)

                        # If files were extracted to a subdirectory, move them to the target directory
                        if root_dir:
                            extract_dir = dest_file.parent / root_dir
                            if extract_dir.exists() and extract_dir != dest_file:
                                # If target directory exists and different from extract_dir
                                # Move contents from extract_dir to dest_file
                                for item in extract_dir.iterdir():
                                    if dest_file.exists():
                                        shutil.move(str(item), str(dest_file))
                                    else:
                                        # Rename extract_dir to dest_file if dest_file doesn't exist
                                        extract_dir.rename(dest_file)
                                        break

                                # Remove the now-empty extracted directory if it still exists
                                if extract_dir.exists():
                                    shutil.rmtree(extract_dir)

                    # Clean up the temporary file
                    os.unlink(temp_file_path)

                    logger.info(f"Successfully extracted repository to {dest_file}")
                    return dest_file

        except httpx.RequestError as e:
            error_msg = f"Error during request to Gitea: {str(e)}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        except Exception as e:
            error_msg = f"Unexpected error when downloading repository: {str(e)}"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
