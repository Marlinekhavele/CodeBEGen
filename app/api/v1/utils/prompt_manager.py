import logging
from typing import Dict, Optional

from langchain.prompts import PromptTemplate

logger = logging.getLogger(__name__)


class PromptManager:
    """Manager for organizing and retrieving prompt templates with language support"""

    # Store templates after loading and processing them
    _templates: Dict[str, Dict[str, PromptTemplate]] = {}
    _initialized: bool = False

    @staticmethod
    def load_templates():
        """Load templates from prompt_templates.py and language-specific templates"""
        if PromptManager._initialized:
            return

        # Load basic Python templates
        # Load API docs and Dockerfile templates
        from app.api.v1.utils.docker_api_templates import (
            API_DOCS_GENERATION_TEMPLATE,
            DOCKERFILE_GENERATION_TEMPLATE,
        )
        from app.api.v1.utils.prompt_templates_py import (
            ENDPOINT_GENERATION_TEMPLATE,
            HELPER_FUNCTIONS_TEMPLATE,
            MIGRATION_GENERATION_TEMPLATE,
            MODEL_GENERATION_TEMPLATE,
            PYTHON_MODEL_CHANGES_TEMPLATE,
            SCHEMA_GENERATION_TEMPLATE,
        )

        # Load language-specific templates if available
        try:
            from app.api.v1.utils.prompt_templates_js import (
                JS_ENDPOINT_GENERATION_TEMPLATE,
                JS_HELPER_FUNCTIONS_TEMPLATE,
                JS_MIGRATION_GENERATION_TEMPLATE,
                JS_MODEL_CHANGES_TEMPLATE,
                JS_MODEL_GENERATION_TEMPLATE,
                JS_SCHEMA_GENERATION_TEMPLATE,
                ROUTES_GENERATION_TEMPLATE,
            )

            has_js_templates = True
        except ImportError:
            logger.warning(
                "JavaScript templates not found. Using Python templates as fallback."
            )
            has_js_templates = False

        # Process templates to escape literal curly braces
        # This is necessary when templates contain code examples with curly braces
        def escape_template_braces(template_string):
            import re

            # Define valid placeholders in the template
            placeholders = [
                "endpoint_description",
                "method",
                "method_lower",
                "endpoint_path",
                "additional_context",
                "language",
                "entity_name",
                "entity_description",
                "endpoint_code",
                "model_code",
                "schema_code",
                "latest_migration_id",
                "prompt_description",
                "existing_model_code",
                "endpoint_context",
                "project_id",
            ]

            # Create a pattern to identify valid placeholders
            pattern = r"\{(" + "|".join(placeholders) + r")\}"

            # Step 1: Temporarily replace valid placeholders
            temp = re.sub(pattern, r"###\1###", template_string)

            # Step 2: Escape all remaining curly braces
            temp = temp.replace("{", "{{").replace("}", "}}")

            # Step 3: Restore the valid placeholders
            for placeholder in placeholders:
                temp = temp.replace(f"###{placeholder}###", f"{{{placeholder}}}")

            return temp

        # Initialize the templates dictionary with escaped templates
        PromptManager._templates = {
            "python": {
                "endpoint": PromptTemplate.from_template(ENDPOINT_GENERATION_TEMPLATE),
                "model": PromptTemplate.from_template(MODEL_GENERATION_TEMPLATE),
                "schema": PromptTemplate.from_template(SCHEMA_GENERATION_TEMPLATE),
                "migration": PromptTemplate.from_template(
                    MIGRATION_GENERATION_TEMPLATE
                ),
                "helpers": PromptTemplate.from_template(HELPER_FUNCTIONS_TEMPLATE),
                "model_changes": PromptTemplate.from_template(
                    escape_template_braces(PYTHON_MODEL_CHANGES_TEMPLATE)
                ),
                "api_docs": PromptTemplate.from_template(
                    escape_template_braces(API_DOCS_GENERATION_TEMPLATE)
                ),
                "dockerfile": PromptTemplate.from_template(
                    escape_template_braces(DOCKERFILE_GENERATION_TEMPLATE)
                ),
            }
        }

        # Add JavaScript templates if available
        if has_js_templates:
            PromptManager._templates["javascript"] = {
                "endpoint": PromptTemplate.from_template(
                    escape_template_braces(JS_ENDPOINT_GENERATION_TEMPLATE)
                ),
                "model": PromptTemplate.from_template(
                    escape_template_braces(JS_MODEL_GENERATION_TEMPLATE)
                ),
                "schema": PromptTemplate.from_template(
                    escape_template_braces(JS_SCHEMA_GENERATION_TEMPLATE)
                ),
                "migration": PromptTemplate.from_template(
                    escape_template_braces(JS_MIGRATION_GENERATION_TEMPLATE)
                ),
                "helpers": PromptTemplate.from_template(
                    escape_template_braces(JS_HELPER_FUNCTIONS_TEMPLATE)
                ),
                "route": PromptTemplate.from_template(
                    escape_template_braces(ROUTES_GENERATION_TEMPLATE)
                ),
                "model_changes": PromptTemplate.from_template(
                    escape_template_braces(JS_MODEL_CHANGES_TEMPLATE)
                ),
                "api_docs": PromptTemplate.from_template(
                    escape_template_braces(API_DOCS_GENERATION_TEMPLATE)
                ),
                "dockerfile": PromptTemplate.from_template(
                    escape_template_braces(DOCKERFILE_GENERATION_TEMPLATE)
                ),
            }

        PromptManager._initialized = True
        logger.info(
            f"Prompt templates loaded for languages: {list(PromptManager._templates.keys())}"
        )

    @staticmethod
    def get_template(
        template_name: str, language: str = "python"
    ) -> Optional[PromptTemplate]:
        """
        Get a template by name and language, loading templates if needed.

        Args:
            template_name: The name of the template (endpoint, model, schema, etc.)
            language: The programming language (python, javascript, etc.)

        Returns:
            PromptTemplate or None if not found
        """
        if not PromptManager._initialized:
            PromptManager.load_templates()

        # Convert language to lowercase for consistency
        language = language.lower()

        # If we don't have templates for the requested language, fallback to python
        if language not in PromptManager._templates:
            logger.warning(
                f"No templates found for language '{language}'. Falling back to python."
            )
            language = "python"

        # Get the template for the specified language
        if template_name in PromptManager._templates[language]:
            return PromptManager._templates[language][template_name]

        logger.error(f"Template '{template_name}' not found for language '{language}'")
        return None

    @staticmethod
    def format_template(template_name: str, language: str, **kwargs) -> str:
        """
        Format a template with the provided variables.

        Args:
            template_name: The name of the template to format
            language: The programming language for the template
            **kwargs: Variables to format the template with

        Returns:
            Formatted template string

        Raises:
            ValueError: If the template is not found
        """
        template = PromptManager.get_template(template_name, language)
        if not template:
            raise ValueError(
                f"Template '{template_name}' not found for language '{language}'"
            )

        # Include language in the formatting kwargs
        format_kwargs = {"language": language, **kwargs}
        return template.format(**format_kwargs)

    @staticmethod
    def add_custom_template(
        template_name: str, template_string: str, language: str = "python"
    ):
        """
        Add a custom template to the manager.

        Args:
            template_name: The name for the new template
            template_string: The template string
            language: The programming language for the template

        Returns:
            None
        """
        if not PromptManager._initialized:
            PromptManager.load_templates()

        language = language.lower()

        # Create language dict if it doesn't exist
        if language not in PromptManager._templates:
            PromptManager._templates[language] = {}

        # Process the template to escape curly braces properly
        def escape_template_braces(template_string):
            import re

            # Define valid placeholders in the template
            placeholders = [
                "endpoint_description",
                "method",
                "method_lower",
                "endpoint_path",
                "additional_context",
                "language",
                "entity_name",
                "entity_description",
                "endpoint_code",
                "model_code",
                "schema_code",
                "latest_migration_id",
            ]

            # Create a pattern to identify valid placeholders
            pattern = r"\{(" + "|".join(placeholders) + r")\}"

            # Step 1: Temporarily replace valid placeholders
            temp = re.sub(pattern, r"###\1###", template_string)

            # Step 2: Escape all remaining curly braces
            temp = temp.replace("{", "{{").replace("}", "}}")

            # Step 3: Restore the valid placeholders
            for placeholder in placeholders:
                temp = temp.replace(f"###{placeholder}###", f"{{{placeholder}}}")

            return temp

        # Add the template
        PromptManager._templates[language][template_name] = (
            PromptTemplate.from_template(escape_template_braces(template_string))
        )
        logger.info(
            f"Added custom template '{template_name}' for language '{language}'"
        )
