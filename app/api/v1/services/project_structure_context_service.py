"""
Project Structure Context Service

This service integrates project structure awareness into the code generation process,
providing context about the project folder structure to the LLM to improve generation quality.
"""

import logging
from functools import lru_cache
from typing import Any, Dict

from app.api.v1.utils.endpoint_services import get_project_dir_from_repo_url
from app.api.v1.utils.git_utils import get_repo_url
from app.api.v1.utils.project_structure import get_formatted_project_structure

logger = logging.getLogger(__name__)


class ProjectStructureContextService:
    """
    Service for retrieving and formatting project structure as context for LLMs.

    This service:
    1. Retrieves the project structure for a given project ID
    2. Formats it for inclusion in LLM prompts
    3. Caches the structure to avoid repeated analysis
    4. Handles large structures through truncation or summarization
    """

    # Cache project structures to avoid repeated analysis
    @staticmethod
    @lru_cache(maxsize=32)
    def get_project_structure_context(project_id: str) -> Dict[str, Any]:
        """
        Get the project structure as context for LLM prompts.
        Uses LRU caching to avoid repeated structure analysis.

        Args:
            project_id: The project identifier

        Returns:
            Dictionary containing the project structure context

        Raises:
            ValueError: If the project directory cannot be found
        """
        try:
            # Get the project directory
            repo_url = get_repo_url(project_id)
            project_dir = get_project_dir_from_repo_url(repo_url)

            if not project_dir.exists():
                raise ValueError(f"Project directory not found: {project_dir}")

            # Get formatted project structure
            formatted_structure = get_formatted_project_structure(project_dir)

            return {
                "project_id": project_id,
                "project_structure": formatted_structure,
                "project_dir": str(project_dir),
            }

        except Exception as e:
            logger.error(f"Error getting project structure context: {e}")
            # Return a minimal context when there's an error
            return {
                "project_id": project_id,
                "project_structure": "Project structure could not be retrieved.",
                "error": str(e),
            }

    @staticmethod
    def enhance_prompt_with_structure(prompt: str, project_id: str) -> str:
        """
        Enhance a prompt with project structure context.

        Args:
            prompt: Original prompt text
            project_id: The project identifier

        Returns:
            Enhanced prompt with project structure context
        """
        try:
            context = ProjectStructureContextService.get_project_structure_context(
                project_id
            )
            project_structure = context["project_structure"]

            enhanced_prompt = f"""
Please consider the following project structure when generating code:

{project_structure}

{prompt}
"""
            return enhanced_prompt

        except Exception as e:
            logger.error(f"Error enhancing prompt with project structure: {e}")
            return prompt

    @staticmethod
    def clear_cache() -> None:
        """
        Clear the project structure cache.
        Call this when a project structure has changed significantly.
        """
        # Get the reference to the cached function
        cached_func = ProjectStructureContextService.get_project_structure_context

        # Clear the LRU cache
        if hasattr(cached_func, "cache_clear"):
            cached_func.cache_clear()
            logger.info("Project structure context cache cleared")
