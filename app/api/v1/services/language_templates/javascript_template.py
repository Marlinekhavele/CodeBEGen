import datetime
import logging
import re
from typing import Any, Dict, List, Optional

from app.api.v1.services.langchain_service import LangchainService
from app.api.v1.services.language_templates.language_template import LanguageTemplate

logger = logging.getLogger(__name__)


class JavaScriptTemplate(LanguageTemplate):
    """JavaScript-specific implementation of language template"""

    def get_file_extension(self) -> str:
        """
        Get the standard file extension for JavaScript files.

        Returns:
            str: File extension for JavaScript ("js")
        """
        return "js"

    def get_component_map(self) -> Dict[str, Optional[str]]:
        """
        Map abstract components to JavaScript-specific components.

        Returns:
            Dict[str, Optional[str]]: Mapping of abstract component types to JavaScript-specific ones
        """
        return {
            "endpoint": "controller",  # In JS, endpoints are controllers
            "model": "model",
            "schema": "validation",  # JS uses validation schemas
            "migration": "migration",
            "helpers": "utils",
            "route": "route",  # Express.js has separate route files
        }

    def get_required_components(self) -> List[str]:
        """
        Get components required for JavaScript Express applications.

        Returns:
            List[str]: List of required JavaScript component types
        """
        return ["controller", "model", "validation", "utils", "route"]

    def needs_database(self, code: str) -> bool:
        """
        Check if the JavaScript controller code needs database models.

        Args:
            code (str): The JavaScript code to analyze

        Returns:
            bool: True if the code references database operations
        """
        db_patterns = [
            r"require\(['\"]\.\./models/",
            r"import\s+.*\s+from\s+['\"]\.\./models/",
            r"mongoose",
            r"sequelize",
            r"Model\.",
            r"\.model\(",
            r"\.findOne\(",
            r"\.findById\(",
            r"\.create\(",
            r"\.find\(",
            r"\.update",
            r"\.delete",
        ]

        for pattern in db_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return True
        return False

    def get_component_paths(
        self, project_id: str, entity_name: str, **kwargs
    ) -> Dict[str, str]:
        """
        Get file paths for JavaScript components.

        Args:
            project_id (str): Identifier for the project being modified
            entity_name (str): Name of the entity to generate paths for

        Returns:
            Dict[str, str]: Mapping of component types to their file paths
        """
        pascal_case_entity = self._to_pascal_case(entity_name)
        kebab_case_entity = self._to_kebab_case(entity_name)

        # For controllers/endpoints, use the endpoint path and method from kwargs if available
        endpoint_path = kwargs.get("endpoint_path", "")
        method = kwargs.get("method", "").lower()

        if endpoint_path and method:
            # Extract the last segment of the path for the filename
            path_segments = endpoint_path.strip("/").split("/")
            last_segment = path_segments[-1] if path_segments else kebab_case_entity
            controller_file = f"controllers/{last_segment}.{method}.js"
        else:
            # Fallback to entity-based naming
            controller_file = f"controllers/{kebab_case_entity}.controller.js"

        return {
            "controller": controller_file,
            "model": f"models/{pascal_case_entity}.js",
            "validation": f"utils/{kebab_case_entity}.validation.js",
            "migration": f"migrations/{self._generate_migration_name(kebab_case_entity)}.js",
            "utils": f"utils/{kebab_case_entity}.utils.js",
            "route": f"routes/{kebab_case_entity}.routes.js",
        }

    def extract_entity_from_code(self, code: str) -> Optional[str]:
        """
        Extract entity name from JavaScript code.

        Args:
            code (str): The JavaScript code to analyze

        Returns:
            Optional[str]: Extracted entity name or None if no entity could be identified
        """
        # CommonJS import pattern
        model_import = re.search(
            r"(const|let|var)\s+(\w+)\s*=\s*require\(['\"]\.\.\/models\/(\w+)['\"]",
            code,
        )
        if model_import:
            return model_import.group(3)

        # ES6 import pattern
        es6_import = re.search(
            r"import\s+(\w+)\s+from\s+['\"]\.\.\/models\/(\w+)['\"]", code
        )
        if es6_import:
            return es6_import.group(2)

        # Mongoose model definition
        mongoose_model = re.search(r"mongoose\.model\(['\"](\w+)['\"]", code)
        if mongoose_model:
            return mongoose_model.group(1)

        # Controller name as fallback
        controller_name = re.search(r"// (\w+) Controller", code)
        if controller_name:
            return controller_name.group(1)

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
            r"\bfor managing (\w+)",  # for managing users
            r"\bto manage (\w+)",  # to manage users
            r"\bfor (\w+)",  # for users
            r"\bto create (\w+)",  # to create cars
            r"\bto delete (\w+)",  # to delete accounts
            r"\babout (\w+)",  # about employees
            r"\bof (\w+)",  # list of cars
            r"\bwith (\w+)",  # with employees
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
        Generate a specific JavaScript component using PromptManager templates.

        Args:
            component_type (str): Type of component to generate
            project_id (str): Identifier for the project being modified
            entity_name (str): Name of the entity the component is for
            entity_description (str): Natural language description of the entity
            **kwargs: Additional parameters for component generation

        Returns:
            Dict[str, Any]: Component data including generated code and metadata

        Raises:
            ValueError: If an unknown component type is requested
        """
        # Map component types to PromptManager template names
        template_map = {
            "controller": "endpoint",
            "model": "model",
            "validation": "schema",
            "migration": "migration",
            "utils": "helpers",
            "route": "route",
        }

        # For components with templates in PromptManager
        if component_type in template_map:
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
                "endpoint_code": kwargs.get("endpoint_code", "")
                or kwargs.get("controller_code", ""),
                "model_code": kwargs.get("model_code", ""),
                "schema_code": kwargs.get("schema_code", ""),
                "latest_migration_id": kwargs.get(
                    "latest_migration_id",
                    "migration_" + datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
                ),
            }

            # Generate code using PromptManager template
            result = await LangchainService.generate_code_with_template(
                template_name=template_name, language="javascript", **template_vars
            )

            # Add language-specific metadata
            result["file_path"] = self.get_component_paths(
                project_id, entity_name, **kwargs
            )[component_type]
            result["entity_name"] = entity_name

            if "method" in kwargs:
                result["method"] = kwargs["method"]
            if "endpoint_path" in kwargs:
                result["endpoint_path"] = kwargs["endpoint_path"]

            return result

        # If we get here, it's an unknown component type
        raise ValueError(f"Unknown component type: {component_type}")

    async def _generate_route(
        self,
        project_id: str,
        entity_name: str,
        entity_description: str,
        controller_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a JavaScript Express route file using PromptManager templates.

        Args:
            project_id (str): Identifier for the project being modified
            entity_name (str): Name of the entity to create routes for
            entity_description (str): Natural language description of the entity
            controller_code (Optional[str]): Optional controller code to extract routes from

        Returns:
            Dict[str, Any]: Route component data including generated code and metadata
        """
        # Prepare template variables
        template_vars = {
            "entity_name": entity_name,
            "entity_description": entity_description,
            "endpoint_description": entity_description,
            "endpoint_code": controller_code or "",
        }

        # Generate code using the route template from PromptManager
        result = await LangchainService.generate_code_with_template(
            template_name="route", language="javascript", **template_vars
        )

        # Add language-specific metadata
        result["file_path"] = self.get_component_paths(project_id, entity_name)["route"]
        result["entity_name"] = entity_name

        return result

    def get_commit_strategy(self) -> Dict[str, Any]:
        """
        Get commit strategy for JavaScript components.

        Returns:
            Dict[str, Any]: Commit strategy with component order and message templates
        """
        return {
            "components": [
                "model",
                "controller",
                "validation",
                "utils",
                "route",
                "migration",
                "dockerfile",
                "api_docs",
            ],
            "commit_order": [
                "model",
                "validation",
                "utils",
                "controller",
                "route",
                "migration",
                "dockerfile",
                "api_docs",
            ],
            "commit_messages": {
                "controller": "Add {entity_name} controller",
                "model": "Add {entity_name} model",
                "validation": "Add validation schemas for {entity_name}",
                "utils": "Add utility functions for {entity_name}",
                "route": "Add routes for {entity_name} API",
                "migration": "Add database migration for {entity_name}",
                "dockerfile": "Add Dockerfile for {entity_name}",
                "api_docs": "Add API documentation for {entity_name}",
            },
        }

    def _to_pascal_case(self, name: str) -> str:
        """
        Convert string to PascalCase.

        Args:
            name (str): Input string to convert

        Returns:
            str: String converted to PascalCase
        """
        # First convert to camelCase
        camel = "".join(word.capitalize() for word in re.split(r"[_\-\s]", name))
        # Ensure first letter is uppercase
        return camel[0].upper() + camel[1:]

    def _to_kebab_case(self, name: str) -> str:
        """
        Convert string to kebab-case.

        Args:
            name (str): Input string to convert

        Returns:
            str: String converted to kebab-case
        """
        # Convert camelCase or PascalCase to kebab-case
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1-\2", name)
        s2 = re.sub("([a-z0-9])([A-Z])", r"\1-\2", s1).lower()
        # Replace underscores and spaces with hyphens
        return re.sub(r"[_\s]", "-", s2).lower()

    def _generate_migration_name(self, entity_name: str) -> str:
        """
        Generate a timestamped migration name.

        Args:
            entity_name (str): Name of the entity for the migration

        Returns:
            str: Timestamped migration name
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{timestamp}-create-{entity_name}"
    
    def run_migrations(self, project_path: str, **kwargs) -> bool:
        """
        Implementation of the abstract method to handle JavaScript migrations.
        
        Args:
            project_path (str): Path to the project
            **kwargs: Additional parameters
            
        Returns:
            bool: True if migrations are successful or ignored, False otherwise
        """
        logger.info("JavaScript migrations are being ignored as requested")
        return True
    def _to_snake_case(self, name: str) -> str:
        """
        Convert string to snake_case.

        Args:
            name (str): Input string to convert

        Returns:
            str: String converted to snake_case
        """
        # First handle camelCase and PascalCase
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
        # Replace hyphens and spaces with underscores
        return re.sub(r'[-\s]', '_', s2).lower()

    async def generate_dockerfile(self, project_id: str, entity_name: str) -> str:
        """
        Generate a Dockerfile for JavaScript/Node.js application.

        Args:
            project_id (str): The project ID
            entity_name (str): The name of the entity

        Returns:
            str: Dockerfile content
        """
        try:
            # Use the prompt template via LangchainService
            result = LangchainService.generate_code_with_template(
                template_name="dockerfile",
                language="javascript",
                project_id=project_id,
                entity_name=entity_name,
            )

            return result["generated_code"]
        except Exception as e:
            logger.error(f"Error generating Dockerfile: {str(e)}")
            # Fallback to a default Dockerfile if generation fails
            return """FROM node:18-slim
    WORKDIR /app
    COPY package*.json ./
    RUN npm install
    COPY . .
    # Run migrations if applicable
    RUN npm run migrate || true
    # Start the server
    EXPOSE 8000
    CMD ["npm", "start"]
    """
