from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Tuple


class FieldChangeType(Enum):
    """Enumeration of possible field change types"""

    ADD = "add"
    MODIFY = "modify"
    REMOVE = "remove"
    RENAME = "rename"


class ModelUpdater(ABC):
    """Abstract base class for language-specific model updaters"""

    @abstractmethod
    def parse_model_structure(
        self, model_code: str, entity_name: str
    ) -> Dict[str, Any]:
        """
        Parse the structure of a model file to identify key positions

        Args:
            model_code: The source code of the model file
            entity_name: The name of the entity being modified

        Returns:
            Dictionary containing the model structure, including positions of fields,
            imports, class definitions, etc.
        """
        pass

    @abstractmethod
    def update_model(
        self,
        model_path: Path,
        entity_name: str,
        field_changes: List[Dict[str, Any]],
        existing_model_code: str,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Update a model file with the specified changes

        Args:
            model_path: Path to the model file
            entity_name: Name of the entity being modified
            field_changes: List of changes to apply
            existing_model_code: Current content of the model file

        Returns:
            Tuple containing:
            - Updated model code
            - Dictionary with change summary
        """
        pass


class SchemaUpdater(ABC):
    """Abstract base class for language-specific schema updaters"""

    @abstractmethod
    def find_schemas(
        self, schema_content: str, entity_name: str
    ) -> List[Dict[str, Any]]:
        """
        Find schemas related to an entity in the content

        Args:
            schema_content: The content of the schema file
            entity_name: The name of the entity being modified

        Returns:
            List of schema information dictionaries, each containing:
            - start_pos: Start position of the schema in the file
            - end_pos: End position of the schema in the file
            - name: Name of the schema
            - fields: Dictionary of fields and their positions
        """
        pass

    @abstractmethod
    def update_schema(
        self,
        schema_content: str,
        schema_info: Dict[str, Any],
        field_changes: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Update a schema with the specified changes

        Args:
            schema_content: The content of the schema file
            schema_info: Information about the schema structure
            field_changes: List of changes to apply

        Returns:
            Dictionary containing:
            - updated: Boolean indicating if changes were made
            - content: Updated schema content
        """
        pass

    @abstractmethod
    def convert_model_changes_to_schema_changes(
        self, model_changes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Convert model field changes to appropriate schema field changes

        Args:
            model_changes: List of model field changes

        Returns:
            List of schema field changes with converted definitions
        """
        pass


class ModelSchemaManagerFactory:
    """Factory for creating language-specific model and schema updaters"""

    @staticmethod
    def get_model_updater(language: str) -> ModelUpdater:
        """
        Get a model updater for the specified language

        Args:
            language: The programming language (e.g., "python", "javascript")

        Returns:
            Appropriate ModelUpdater instance for the language
        """
        if language.lower() == "python":
            from app.api.v1.services.model_schema_update.python_model import (
                PythonModelUpdater,
            )

            return PythonModelUpdater()
        elif language.lower() in ["javascript", "js"]:
            from app.api.v1.services.model_schema_update.javascript_model import (
                JavaScriptModelUpdater,
            )

            return JavaScriptModelUpdater()
        else:
            import logging

            logging.getLogger(__name__).warning(
                f"Unsupported language for model updates: {language}. Falling back to Python."
            )
            from app.api.v1.services.model_schema_update.python_model import (
                PythonModelUpdater,
            )

            return PythonModelUpdater()

    @staticmethod
    def get_schema_updater(language: str, schema_type: str = None) -> SchemaUpdater:
        """
        Get a schema updater for the specified language and schema type

        Args:
            language: The programming language (e.g., "python", "javascript")
            schema_type: Optional schema type for languages with multiple schema formats

        Returns:
            Appropriate SchemaUpdater instance for the language and schema type
        """
        if language.lower() == "python":
            from app.api.v1.services.model_schema_update.python_schema import (
                PydanticSchemaUpdater,
            )

            return PydanticSchemaUpdater()
        elif language.lower() in ["javascript", "js"]:
            if schema_type == "joi":
                from app.api.v1.services.model_schema_update.javascript_schema import (
                    JoiSchemaUpdater,
                )

                return JoiSchemaUpdater()
            elif schema_type == "express-validator":
                from app.api.v1.services.model_schema_update.javascript_schema import (
                    ExpressValidatorSchemaUpdater,
                )

                return ExpressValidatorSchemaUpdater()
            else:
                from app.api.v1.services.model_schema_update.javascript_schema import (
                    GenericJSSchemaUpdater,
                )

                return GenericJSSchemaUpdater()
        else:
            import logging

            logging.getLogger(__name__).warning(
                f"Unsupported language for schema updates: {language}. Falling back to Python."
            )
            from app.api.v1.services.model_schema_update.python_schema import (
                PydanticSchemaUpdater,
            )

            return PydanticSchemaUpdater()
