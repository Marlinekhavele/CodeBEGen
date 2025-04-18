import logging
from typing import Any, Dict, List

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.db.database import get_db
from app.api.v1.models.endpoints import EndPoint
from app.api.v1.models.projects import Project
from app.api.v1.utils.git_utils import get_repo_url

logger = logging.getLogger(__name__)


class GetAllEndpoints:
    @staticmethod
    async def get_all_endpoints_from_db(
        project_id: str, db: Session = Depends(get_db)
    ) -> List[Dict[str, Any]]:
        """
        Retrieves all endpoints for a specific project from the database

        Args:
            project_id: The slug of the project
            db: Database session

        Returns:
            List of endpoints with their details
        """
        logger.info(
            f"Retrieving all endpoints for project slug {project_id} from database"
        )

        try:
            project = db.query(Project).filter(Project.slug == project_id).first()

            if not project:
                logger.warning(f"Project with slug {project_id} not found in database")
                return []

            project_uuid = project.id
            logger.info(f"Found project UUID: {project_uuid} for slug: {project_id}")

            endpoints = (
                db.query(EndPoint).filter(EndPoint.project_id == project_uuid).all()
            )

            # Convert to list of dictionaries
            result = []
            for endpoint in endpoints:
                result.append(
                    {
                        "path": endpoint.path,
                        "method": endpoint.method,
                        "description": endpoint.description,
                        "id": endpoint.id,
                    }
                )

            logger.info(
                f"Found {len(result)} endpoints for project {project_id} (UUID: {project_uuid})"
            )
            return result

        except Exception as e:
            logger.error(f"Error retrieving endpoints from database: {str(e)}")
            raise

    @staticmethod
    async def get_all_endpoints_from_repo(
        project_id: str, db: Session
    ) -> List[Dict[str, Any]]:
        """
        Retrieves all endpoints for a specific project

        Args:
            project_id: The slug of the project
            db: Database session

        Returns:
            List of endpoints with their details
        """
        try:
            repo_url = get_repo_url(project_id)
            logger.info(
                f"Verified project exists with slug: {project_id}, repo URL: {repo_url}"
            )
            project = db.query(Project).filter(Project.slug == project_id).first()
            if not project:
                logger.warning(f"Project with slug {project_id} not found in database")
                return []
            logger.info(
                f"Found project in database: {project.id} (slug: {project.slug})"
            )
            endpoints = await GetAllEndpoints.get_all_endpoints_from_db(project_id, db)
            logger.info(f"Retrieved {len(endpoints)} endpoints from database")
            if not endpoints:
                logger.warning(
                    f"No endpoints found for project {project_id} (uuid: {project.id})"
                )

            return endpoints

        except ValueError as e:
            logger.error(f"Invalid project slug: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error retrieving endpoints: {str(e)}")
            raise
