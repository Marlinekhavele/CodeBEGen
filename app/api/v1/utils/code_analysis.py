import ast
import logging
from typing import Dict, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# --- AST Visitor for Dependency Analysis ---
class DependencyVisitor(ast.NodeVisitor):
    """
    Traverses Python code AST to find model, schema, and helper dependencies,
    and attempts to identify the primary entity.
    """

    def __init__(self):
        self.dependencies: Dict[str, Set[str]] = {
            "models": set(),
            "schemas": set(),
            "helpers": set(),  # Stores module names like 'user_helpers'
            "other_imports": set(),
        }
        # Score candidates based on import and usage patterns
        self.primary_entity_candidates: Dict[str, int] = {}
        self._current_function_decorators = []

    def _add_candidate_score(self, entity_name: str, score: int):
        """Safely increments score for a potential primary entity."""
        if entity_name and entity_name != "Base":  # Ignore Base model/schema
            # Simple singularization/pluralization check (can be improved)
            if entity_name.endswith("s"):
                base_name = entity_name[:-1]
            else:
                base_name = entity_name
            # Use title case for consistency
            base_name = base_name.title()
            # Avoid adding empty strings or purely numeric names if parsing goes wrong
            if base_name and not base_name.isdigit():
                self.primary_entity_candidates[base_name] = (
                    self.primary_entity_candidates.get(base_name, 0) + score
                )
            else:
                logger.debug(
                    f"Skipping invalid candidate score addition for: '{entity_name}' -> '{base_name}'"
                )

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            module_parts = node.module.split(".")
            first_part = module_parts[0]

            if first_part == "models" and len(module_parts) == 2:
                entity_module = module_parts[1]  # e.g., 'user' from 'models.user'
                self.dependencies["models"].add(entity_module)
                # Imported items (e.g., User from models.user import User)
                for alias in node.names:
                    self._add_candidate_score(alias.name, 1)  # Score 1 for model import

            elif first_part == "schemas" and len(module_parts) == 2:
                entity_module = module_parts[1]  # e.g., 'user' from 'schemas.user'
                self.dependencies["schemas"].add(entity_module)
                for alias in node.names:
                    # Score 1 for schema import (often named like UserSchema)
                    self._add_candidate_score(
                        alias.name.replace("Schema", "")
                        .replace("Create", "")
                        .replace("Update", ""),
                        1,
                    )

            elif first_part == "helpers" and len(module_parts) == 2:
                helper_module = module_parts[1]  # e.g., 'user_helpers'
                self.dependencies["helpers"].add(helper_module)
                # Try to infer entity from helper module name
                entity_name = helper_module.replace("_helpers", "")
                self._add_candidate_score(entity_name, 1)  # Score 1 for helper import

            else:
                # Track other potentially relevant imports if needed
                self.dependencies["other_imports"].add(node.module)

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Look for db.query(ModelName)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "query":
            # Check if the object being called is named 'db' (or similar)
            base_obj = node.func.value
            if isinstance(base_obj, ast.Name) and base_obj.id == "db":
                if node.args and isinstance(node.args[0], ast.Name):
                    model_name = node.args[0].id
                    # Add model name directly as a candidate with high score
                    self._add_candidate_score(
                        model_name, 5
                    )  # Score 5 for direct query usage

        # Could add checks for specific helper function calls here if needed

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Store decorators for context when visiting nodes inside the function
        self._current_function_decorators = node.decorator_list
        # Check decorators for response_model
        for decorator in node.decorator_list:
            # Check for @router.get/post/put/delete/patch(...)
            if isinstance(decorator, ast.Call) and isinstance(
                decorator.func, ast.Attribute
            ):
                if decorator.func.attr in ("get", "post", "put", "delete", "patch"):
                    for keyword in decorator.keywords:
                        if keyword.arg == "response_model":
                            schema_name = self._extract_schema_name_from_node(
                                keyword.value
                            )
                            if schema_name:
                                # Infer entity name (e.g., User from UserSchema)
                                entity_name = schema_name.replace("Schema", "")
                                self._add_candidate_score(
                                    entity_name, 5
                                )  # Score 5 for response_model usage
        # Reset decorators after visiting the function body
        self.generic_visit(node)
        self._current_function_decorators = []

    def _extract_schema_name_from_node(self, node: ast.AST) -> Optional[str]:
        """Helper to get schema name from AST nodes like Name or Subscript (List[X])."""
        if isinstance(node, ast.Name):
            return node.id
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id in ("List", "Optional")
        ):
            # Handle List[SchemaName], Optional[SchemaName]
            # Need to handle potential tuples in slices for Python < 3.9
            slice_node = node.slice
            # Handle Python 3.9+ direct slice vs older Index node
            if isinstance(slice_node, ast.Index):  # Python < 3.9 style
                slice_node = slice_node.value
            # Now slice_node should be the actual type node (e.g., Name)
            if isinstance(slice_node, ast.Name):
                return slice_node.id
            elif isinstance(
                slice_node, ast.Subscript
            ):  # Handle nested types like Optional[List[X]]
                return self._extract_schema_name_from_node(slice_node)
        return None

    def get_analysis_results(self) -> Tuple[Dict[str, Set[str]], Optional[str]]:
        """Returns the collected dependencies and the best guess for the primary entity."""
        primary_entity = None
        if self.primary_entity_candidates:
            # Find the candidate with the highest score
            try:
                primary_entity = max(
                    self.primary_entity_candidates,
                    key=self.primary_entity_candidates.get,
                )
                # Basic validation/cleanup
                if not primary_entity or not primary_entity.isalnum():
                    logger.warning(
                        f"Primary entity candidate '{primary_entity}' failed validation."
                    )
                    primary_entity = None  # Discard if it looks invalid
            except (
                ValueError
            ):  # Handles case where candidates might be empty after filtering
                logger.warning(
                    "No valid primary entity candidates found after scoring."
                )
                primary_entity = None

        return self.dependencies, primary_entity
