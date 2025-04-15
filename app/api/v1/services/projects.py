import hashlib
import logging
import random
import string
from pathlib import Path

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.db.database import get_db
from app.api.v1.models.endpoints import EndPoint
from app.api.v1.models.projects import Project
from app.api.v1.schemas.projects import ProjectInitRequest, ProjectInitResponse
from app.api.v1.utils.git_operations import (
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
        framework = init_request.framework

        # Create Gitea repository (if credentials are provided)
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
                update_git_remote(project_dir, repo_url)

                # Push the code to the new repository
                push_to_remote(project_dir)

                logger.info(
                    f"Successfully initialized project {slug} with repository {repo_url}"
                )
            except Exception as e:
                # Log the error but continue with the process
                logger.error(f"Error during repository setup: {str(e)}")
                # If we have a partial repo_url but the process failed, we should still return it

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
                # Continue with the process even if database operations fail
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
        return ProjectInitResponse(project_id=slug, project_url=project_url,language=language,framework=framework)
