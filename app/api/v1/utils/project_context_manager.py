"""
Project Context Manager

This module provides functionality to inject project structure context into LLM prompts.
It's designed to be integrated with the existing API flow for code generation.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, Union

from langchain.prompts import PromptTemplate

from app.api.v1.utils.project_structure import get_formatted_project_structure

logger = logging.getLogger(__name__)


class ProjectContextManager:
    """
    Manages project context for LLM prompts.
    """

    @staticmethod
    def get_project_context(project_path: Union[str, Path]) -> str:
        """
        Get formatted project structure as context for LLM prompts.

        Args:
            project_path: Path to the project root

        Returns:
            Formatted project structure string
        """
        return get_formatted_project_structure(project_path)

    @staticmethod
    @lru_cache(maxsize=32)
    def get_project_context_system_message(
        project_id: str, project_path: Union[str, Path]
    ) -> Dict[str, str]:
        """
        Get a system message with project context for the LLM.
        Uses LRU cache to avoid redundant structure analysis.

        Args:
            project_id: Unique identifier for the project
            project_path: Path to the project root

        Returns:
            Dictionary with system message
        """
        try:
            project_structure = get_formatted_project_structure(project_path)

            system_message = {
                "role": "system",
                "content": f"""You are a code generation assistant with knowledge of the project structure.

{project_structure}

Please use this project structure context to provide accurate, project-specific answers.
When generating code, ensure it aligns with the existing structure and follows similar patterns.
""",
            }
            return system_message

        except Exception as e:
            logger.error(f"Error creating project context system message: {e}")
            return {
                "role": "system",
                "content": "You are a code generation assistant. Project structure information is not available.",
            }

    @staticmethod
    def enhance_prompt_with_project_context(
        prompt_template: Union[str, PromptTemplate],
        project_path: Union[str, Path],
        template_vars: Dict = None,
    ) -> Union[str, PromptTemplate]:
        """
        Enhance a prompt template with project context information.

        Args:
            prompt_template: The original prompt template
            project_path: Path to the project root
            template_vars: Variables to be used with the template

        Returns:
            Enhanced prompt template with project structure context
        """
        project_structure = get_formatted_project_structure(project_path)

        if isinstance(prompt_template, str):
            context_header = f"""
Please consider the following project structure when responding:

{project_structure}

"""
            enhanced_template = context_header + prompt_template
            return enhanced_template

        elif isinstance(prompt_template, PromptTemplate):
            # Get the original template string and variables
            original_template = prompt_template.template
            variables = prompt_template.input_variables

            # Add project structure context to the template
            context_header = f"""
Please consider the following project structure when responding:

{project_structure}

"""
            enhanced_template = context_header + original_template

            # Create a new template with the same variables
            return PromptTemplate(template=enhanced_template, input_variables=variables)

        else:
            logger.warning(f"Unsupported prompt template type: {type(prompt_template)}")
            return prompt_template
