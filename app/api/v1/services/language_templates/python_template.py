import re
from typing import Any, Dict, List, Optional

from app.api.v1.services.langchain_service import LangchainService
from app.api.v1.services.language_templates.language_template import LanguageTemplate


class PythonTemplate(LanguageTemplate):
    """Python-specific implementation of language template"""

    def get_file_extension(self) -> str:
        """
        Get the standard file extension for Python files.

        Returns:
            str: File extension for Python ("py")
        """
        return "py"

    def get_component_map(self) -> Dict[str, Optional[str]]:
        """
        Map abstract components to Python-specific components.

        Returns:
            Dict[str, Optional[str]]: Mapping of abstract component types to Python-specific ones
        """
        return {
            "endpoint": "endpoint",
            "model": "model",
            "schema": "schema",
            "migration": "migration",
            "helpers": "helpers",
            "route": None,  # Python FastAPI combines routes and endpoints
        }

    def get_required_components(self) -> List[str]:
        """
        Get components required for Python FastAPI applications.

        Returns:
            List[str]: List of required Python component types
        """
        return ["endpoint", "model", "schema", "migration", "helpers"]

    def needs_database(self, code: str) -> bool:
        """
        Check if the Python endpoint code needs database models.

        Args:
            code (str): The Python code to analyze

        Returns:
            bool: True if the code references database operations
        """
        db_patterns = [
            r"from\s+.*models?\s+import",
            r"from\s+.*schemas?\s+import",
            r"from\s+.*database\s+import",
            r"db\.session",
            r"db\s*\.\s*query",
            r"Model\(",
            r"SQLAlchemy",
            r"Base\.",
            r"@sqlalchemy_to_pydantic",
        ]

        for pattern in db_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return True
        return False

    def get_component_paths(self, project_id: str, entity_name: str) -> Dict[str, str]:
        """
        Get file paths for Python components based on project conventions.

        Args:
            project_id (str): Identifier for the project being modified
            entity_name (str): Name of the entity to generate paths for

        Returns:
            Dict[str, str]: Mapping of component types to their file paths
        """
        snake_case_entity = self._to_snake_case(entity_name)

        return {
            "endpoint": f"endpoints/{snake_case_entity}_endpoint.py",
            "model": f"models/{snake_case_entity}.py",
            "schema": f"schemas/{snake_case_entity}_schema.py",
            "migration": f"alembic/versions/create_{snake_case_entity}_table.py",
            "helpers": f"helpers/{snake_case_entity}_helpers.py",
        }

    def extract_entity_from_code(self, code: str) -> Optional[str]:
        """
        Extract entity name from Python code using regex patterns.

        Args:
            code (str): The Python code to analyze

        Returns:
            Optional[str]: Extracted entity name or None if no entity could be identified
        """
        # Pattern for model imports
        model_import = re.search(r"from\s+.*models?\s+import\s+(\w+)", code)
        if model_import:
            return model_import.group(1)

        # Pattern for db queries
        db_query = re.search(r"db\.query\((\w+)\)", code)
        if db_query:
            return db_query.group(1)

        # Pattern for schema usage
        schema_usage = re.search(r"(\w+)Schema\(", code)
        if schema_usage:
            return schema_usage.group(1)

        # Pattern for model instantiation
        model_inst = re.search(r"(\w+)\s*=\s*\w+Model\(", code)
        if model_inst:
            return model_inst.group(1)

        # Pattern for model class definition
        model_class = re.search(r"class\s+(\w+)\s*\(\s*Base\s*\)", code)
        if model_class:
            return model_class.group(1)

        return None

    def extract_entity_from_prompt(self, prompt: str) -> Optional[str]:
        """
        Extract an entity name from a natural language prompt.
        Returns a single entity name as a string.
        """
        import re
        prompt = prompt.lower()
        
        # Regex patterns to match different common phrases
        patterns = [
            r'\bfor managing (\w+)',             # for managing users
            r'\bto manage (\w+)',                # to manage users
            r'\bfor (\w+)',                      # for users
            r'\bto create (\w+)',                # to create cars
            r'\bto delete (\w+)',                # to delete accounts
            r'\babout (\w+)',                    # about employees
            r'\bof (\w+)',                       # list of cars
            r'\bwith (\w+)',                     # with employees
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, prompt)
            if matches:
                entity = matches[0]
                # Basic plural to singular
                if entity.endswith("ies"):
                    entity = entity[:-3] + "y"
                elif entity.endswith("s") and not entity.endswith("ss"):
                    entity = entity[:-1]
                return entity.capitalize()
        
        # Fallback to capitalized word if no matches found
        match = re.search(r"\b([A-Z][a-zA-Z0-9_]*)\b", prompt)
        return match.group(1) if match else "Temp"

    async def generate_component(
        self,
        component_type: str,
        project_id: str,
        entity_name: str,
        entity_description: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generate a specific Python component using prompt templates.

        Args:
            component_type (str): Type of component to generate (endpoint, model, etc.)
            project_id (str): Identifier for the project being modified
            entity_name (str): Name of the entity the component is for
            entity_description (str): Natural language description of the entity
            **kwargs: Additional parameters for component generation

        Returns:
            Dict[str, Any]: Component data including generated code, file path, and metadata

        Raises:
            ValueError: If an unknown component type is requested
        """
        # Map component types to template names in PromptManager
        template_map = {
            "endpoint": "endpoint",
            "model": "model",
            "schema": "schema",
            "migration": "migration",
            "helpers": "helpers",
        }

        # Check if component type is supported
        if component_type not in template_map:
            raise ValueError(f"Unknown component type: {component_type}")

        # Get the template name
        template_name = template_map[component_type]

        # Prepare template variables
        template_vars = {
            "entity_name": entity_name,
            "entity_description": entity_description,
            "endpoint_description": kwargs.get(
                "entity_description", entity_description
            ),
            "method": kwargs.get("method", "GET"),
            "method_lower": kwargs.get("method", "GET").lower(),
            "endpoint_path": kwargs.get("endpoint_path", ""),
            "additional_context": kwargs.get("additional_context", ""),
            "endpoint_code": kwargs.get("endpoint_code", ""),
            "model_code": kwargs.get("model_code", ""),
            "schema_code": kwargs.get("schema_code", ""),
            "latest_migration_id": kwargs.get("latest_migration_id", ""),
        }

        # Generate code using PromptManager template
        result = await LangchainService.generate_code_with_template(
            template_name=template_name, language="python", **template_vars
        )

        # Add language-specific metadata
        result["file_path"] = self.get_component_paths(project_id, entity_name)[
            component_type
        ]
        result["entity_name"] = entity_name

        if "method" in kwargs:
            result["method"] = kwargs["method"]
        if "endpoint_path" in kwargs:
            result["endpoint_path"] = kwargs["endpoint_path"]

        return result

    def get_commit_strategy(self) -> Dict[str, Any]:
        """
        Get strategy for committing Python components to version control.

        Returns:
            Dict[str, Any]: Commit strategy with component order and message templates
        """
        return {
            "components": ["model", "schema", "migration", "helpers", "endpoint"],
            "commit_order": ["model", "schema", "migration", "helpers", "endpoint"],
            "commit_messages": {
                "endpoint": "Add {method} endpoint for {endpoint_path}",
                "model": "Add {entity_name} model",
                "schema": "Add {entity_name} schema",
                "migration": "Add migration for {entity_name} model",
                "helpers": "Add helper functions for {entity_name}",
            },
        }

    def _to_snake_case(self, name: str) -> str:
        """
        Convert string to snake_case following Python naming conventions.

        Args:
            name (str): Input string to convert

        Returns:
            str: String converted to snake_case
        """
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
