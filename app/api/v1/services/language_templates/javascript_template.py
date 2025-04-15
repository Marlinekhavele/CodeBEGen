import datetime
import re
from typing import Any, Dict, List, Optional

from app.api.v1.services.langchain_service import LangchainService
from app.api.v1.services.language_templates.language_template import LanguageTemplate


class JavaScriptTemplate(LanguageTemplate):
    """JavaScript-specific implementation of language template"""

    def get_file_extension(self) -> str:
        return "js"

    def get_component_map(self) -> Dict[str, Optional[str]]:
        """Map abstract components to JavaScript-specific components"""
        return {
            "endpoint": "controller",  # In JS, endpoints are controllers
            "model": "model",
            "schema": "validation",  # JS uses validation schemas
            "migration": "migration",
            "helpers": "utils",
            "route": "route",  # Express.js has separate route files
        }

    def get_required_components(self) -> List[str]:
        """Get components required for JavaScript Express applications"""
        return ["controller", "model", "validation", "utils", "route"]

    def needs_database(self, code: str) -> bool:
        """Check if the JavaScript controller code needs database models"""
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

    def get_component_paths(self, project_id: str, entity_name: str) -> Dict[str, str]:
        """Get file paths for JavaScript components"""
        pascal_case_entity = self._to_pascal_case(entity_name)
        kebab_case_entity = self._to_kebab_case(entity_name)

        return {
            "controller": f"controllers/{kebab_case_entity}.controller.js",
            "model": f"models/{pascal_case_entity}.js",
            "validation": f"utils/{kebab_case_entity}.validation.js",
            "migration": f"migrations/{self._generate_migration_name(kebab_case_entity)}.js",
            "utils": f"utils/{kebab_case_entity}.utils.js",
            "route": f"routes/{kebab_case_entity}.routes.js",
        }

    def extract_entity_from_code(self, code: str) -> Optional[str]:
        """Extract entity name from JavaScript code"""
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

    async def generate_component(
        self,
        component_type: str,
        project_id: str,
        entity_name: str,
        entity_description: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate a specific JavaScript component using PromptManager templates"""
        # Map component types to PromptManager template names
        template_map = {
            "controller": "endpoint",  # In PromptManager templates, this is called "endpoint"
            "model": "model",
            "validation": "schema",  # In PromptManager templates, this is called "schema"
            "migration": "migration",
            "utils": "helpers",  # In PromptManager templates, this is called "helpers"
        }

        # Route component doesn't have a specific template in PromptManager,
        # so we'll handle it separately
        if component_type == "route":
            return await self._generate_route(
                project_id,
                entity_name,
                entity_description,
                kwargs.get("controller_code"),
            )

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
            result["file_path"] = self.get_component_paths(project_id, entity_name)[
                component_type
            ]
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
        """Generate a JavaScript Express route file"""
        # Create a custom prompt for Express.js routes
        route_prompt = f"""
        Generate an Express.js route file for {entity_name}.
        The entity represents {entity_description}.
        Create routes that map to controller functions.
        Use ES6 syntax and export the router.

        Based on the controller:
        {controller_code if controller_code else 'No controller code provided.'}
        """

        # Use custom generation for JavaScript
        result = await LangchainService.generate_custom_code(
            project_id=project_id,
            prompt=route_prompt,
            language="javascript",
            context=controller_code,
        )

        # Add language-specific metadata
        result["file_path"] = self.get_component_paths(project_id, entity_name)["route"]
        result["entity_name"] = entity_name

        return result

    def get_commit_strategy(self) -> Dict[str, Any]:
        """Get commit strategy for JavaScript components"""
        return {
            "components": [
                "model",
                "controller",
                "validation",
                "utils",
                "route",
                "migration",
            ],
            "commit_order": [
                "model",
                "validation",
                "utils",
                "controller",
                "route",
                "migration",
            ],
            "commit_messages": {
                "controller": "Add {entity_name} controller",
                "model": "Add {entity_name} model",
                "validation": "Add validation schemas for {entity_name}",
                "utils": "Add utility functions for {entity_name}",
                "route": "Add routes for {entity_name} API",
                "migration": "Add database migration for {entity_name}",
            },
        }

    def _to_pascal_case(self, name: str) -> str:
        """Convert string to PascalCase"""
        # First convert to camelCase
        camel = "".join(word.capitalize() for word in re.split(r"[_\-\s]", name))
        # Ensure first letter is uppercase
        return camel[0].upper() + camel[1:]

    def _to_kebab_case(self, name: str) -> str:
        """Convert string to kebab-case"""
        # Convert camelCase or PascalCase to kebab-case
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1-\2", name)
        s2 = re.sub("([a-z0-9])([A-Z])", r"\1-\2", s1).lower()
        # Replace underscores and spaces with hyphens
        return re.sub(r"[_\s]", "-", s2).lower()

    def _generate_migration_name(self, entity_name: str) -> str:
        """Generate a timestamped migration name"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{timestamp}-create-{entity_name}"
