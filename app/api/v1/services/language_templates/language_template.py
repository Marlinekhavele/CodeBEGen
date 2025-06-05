import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class LanguageTemplate(ABC):
    """
    Abstract base class for language-specific code generation templates.
    Each language implements this interface to define its own structure and generation logic.
    """

    @abstractmethod
    def get_file_extension(self) -> str:
        """
        Get file extension for this language.

        Returns:
            str: File extension without the leading dot
        """
        pass

    @abstractmethod
    def get_component_map(self) -> Dict[str, Optional[str]]:
        """
        Map abstract components to language-specific components.

        Returns:
            Dict[str, Optional[str]]: Dictionary mapping abstract component names to
            language-specific component names
        """
        pass

    @abstractmethod
    def get_required_components(self) -> List[str]:
        """
        Get list of components required for this language.

        Returns:
            List[str]: List of component names that should be generated
        """
        pass

    @abstractmethod
    def needs_database(self, code: str) -> bool:
        """
        Determine if generated code needs database components.

        Args:
            code (str): The generated code (usually endpoint/controller)

        Returns:
            bool: True if database components like models should be generated
        """
        pass

    @abstractmethod
    def get_component_paths(self, project_id: str, entity_name: str) -> Dict[str, str]:
        """
        Get file paths for different components based on language conventions.

        Args:
            project_id (str): The project ID
            entity_name (str): The name of the entity/resource

        Returns:
            Dict[str, str]: Dictionary mapping component types to their file paths
        """
        pass

    @abstractmethod
    def extract_entity_from_code(self, code: str) -> Optional[str]:
        """
        Extract entity name from generated code using language-specific patterns.

        Args:
            code (str): The generated code

        Returns:
            Optional[str]: Entity name if found, None otherwise
        """
        pass

    @abstractmethod
    async def run_migrations(self, project_dir: Path, entity_name: str = None):
        """
        Run the migration logic for this language.
        Should be implemented by each concrete template.
        """
        pass

    @abstractmethod
    async def generate_dockerfile(self, project_id: str, entity_name: str) -> str:
        """
        Generate a Dockerfile appropriate for this language/framework.

        Args:
            project_id (str): The project ID
            entity_name (str): The name of the entity

        Returns:
            str: Dockerfile content
        """
        pass

    @abstractmethod
    async def generate_component(
        self,
        component_type: str,
        project_id: str,
        entity_name: str,
        entity_description: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generate a specific component for this language.

        Args:
            component_type (str): Type of component to generate
            project_id (str): The project ID
            entity_name (str): The name of the entity/resource
            entity_description (str): Description of the entity
            **kwargs: Additional parameters needed for generation

        Returns:
            Dict[str, Any]: Dictionary with generated code and metadata
        """
        pass

    @abstractmethod
    def get_commit_strategy(self) -> Dict[str, Any]:
        """
        Get strategy for committing files based on language best practices.

        Returns:
            Dict[str, Any]: Dictionary with commit strategy information
        """
        pass

    def has_component(self, abstract_component: str) -> bool:
        """
        Check if this language supports a given abstract component.

        Args:
            abstract_component (str): The abstract component name

        Returns:
            bool: True if the language has this component, False otherwise
        """
        component_map = self.get_component_map()
        return (
            abstract_component in component_map
            and component_map[abstract_component] is not None
        )

    def get_language_component(self, abstract_component: str) -> Optional[str]:
        """
        Get language-specific component name for an abstract component.

        Args:
            abstract_component (str): The abstract component name

        Returns:
            Optional[str]: Language-specific component name or None if not supported
        """
        component_map = self.get_component_map()
        return component_map.get(abstract_component)

    def get_abstract_components(self) -> Set[str]:
        """
        Get all supported abstract component types.

        Returns:
            Set[str]: Set of abstract component names
        """
        return set(
            key for key, value in self.get_component_map().items() if value is not None
        )

    def get_language_components(self) -> Set[str]:
        """
        Get all language-specific component types.

        Returns:
            Set[str]: Set of language-specific component names
        """
        return set(
            value for value in self.get_component_map().values() if value is not None
        )

    def extract_entity_from_prompt(self, prompt: str) -> str:
        """
        Extract an entity name from a natural language prompt.
        Should be implemented by each language template.
        """
        pass


class LanguageTemplateFactory:
    """Factory for creating language templates."""

    _template_registry = {}

    @classmethod
    def register_template(cls, language: str, template_class):
        """
        Register a template class for a specific language.

        Args:
            language: The language identifier (e.g., 'python', 'javascript')
            template_class: The template class to register
        """
        cls._template_registry[language.lower()] = template_class
        logger.info(f"Registered template for language: {language}")

    @classmethod
    def create_template(cls, language: str, **kwargs):
        """
        Create a language template for the specified language.

        Args:
            language: The programming language to create a template for
            **kwargs: Additional parameters for template instantiation

        Returns:
            LanguageTemplate: An instance of a language-specific template
        """
        language = language.lower()

        # First check the registry
        if language in cls._template_registry:
            return cls._template_registry[language](**kwargs)

        # Fallback to hardcoded templates
        if language == "python":
            from app.api.v1.services.language_templates.python_template import (
                PythonTemplate,
            )

            return PythonTemplate(**kwargs)
        elif language in ["javascript", "js"]:
            from app.api.v1.services.language_templates.javascript_template import (
                JavaScriptTemplate,
            )

            return JavaScriptTemplate(**kwargs)
        else:
            raise ValueError(f"Unsupported language: {language}")

    @classmethod
    def get_template(cls, language: str, **kwargs):
        """
        Retrieve a registered template instance for a specific language.

        Args:
            language: The language identifier (e.g., 'python', 'javascript')
            **kwargs: Additional parameters for template instantiation

        Returns:
            LanguageTemplate: An instance of the registered template class for the language.

        Raises:
            ValueError: If no template is registered for the language.
        """
        language = language.lower()
        if language in cls._template_registry:
            return cls._template_registry[language](**kwargs)
        raise ValueError(f"No template registered for language: {language}")
