import ast
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.api.v1.utils.endpoint_services import get_project_dir_from_repo_url
from app.api.v1.utils.git_utils import get_repo_url

logger = logging.getLogger(__name__)


class ProjectAnalysisService:
    @staticmethod
    async def analyze_project(project_id: str) -> Dict[str, Any]:
        """
        Analyze a project's codebase and return a summary

        Args:
            project_id: The project identifier

        Returns:
            Dictionary containing project analysis
        """
        try:
            # Get the project directory
            repo_url = get_repo_url(project_id)
            project_dir = get_project_dir_from_repo_url(repo_url)

            # Initialize analysis result
            analysis = {
                "project_id": project_id,
                "endpoints": [],
                "models": [],
                "schemas": [],
                "utils": [],
                "summary": "",
            }

            # Analyze endpoints directory - updated to match flat structure
            endpoints_dir = project_dir / "endpoints"
            if endpoints_dir.exists():
                analysis["endpoints"] = ProjectAnalysisService._analyze_endpoints(
                    endpoints_dir
                )

            # Analyze models - updated to match flat structure
            models_dir = project_dir / "models"
            if models_dir.exists():
                analysis["models"] = ProjectAnalysisService._analyze_models(models_dir)

            # Analyze schemas - updated to match flat structure
            schemas_dir = project_dir / "schemas"
            if schemas_dir.exists():
                analysis["schemas"] = ProjectAnalysisService._analyze_schemas(
                    schemas_dir
                )

            # Analyze helpers - new addition to match repository structure
            helpers_dir = project_dir / "helpers"
            if helpers_dir.exists():
                analysis["helpers"] = ProjectAnalysisService._analyze_helpers(
                    helpers_dir
                )

            # Generate a summary
            analysis["summary"] = ProjectAnalysisService._generate_summary(analysis)

            return analysis
        except Exception as e:
            logger.error(f"Error analyzing project: {str(e)}")
            return {"error": str(e)}

    @staticmethod
    def _analyze_endpoints(endpoints_dir: Path) -> List[Dict[str, Any]]:
        """
        Analyze endpoint files in the project to extract API endpoint information.

        This improved method recursively traverses the specified directory to find Python files
        that contain API endpoint definitions. It extracts comprehensive information including
        path, HTTP method, function name, parameters, return type, dependencies, and more.

        Args:
            endpoints_dir (Path): Directory path containing API endpoint files

        Returns:
            List[Dict[str, Any]]: List of endpoint dictionaries with detailed information
        """
        endpoints = []

        logger.info(f"Analyzing endpoints directory: {endpoints_dir}")

        # Check if directory exists
        if not endpoints_dir.exists():
            logger.warning(f"Endpoints directory does not exist: {endpoints_dir}")
            return endpoints

        # Walk through the endpoints directory
        for root, _, files in os.walk(endpoints_dir):
            for file in files:
                if file.endswith(".py"):
                    file_path = Path(root) / file
                    logger.info(f"Examining endpoint file: {file_path}")

                    # Extract the correct path and method from filename
                    # Many FastAPI projects use naming convention like "user.post.py" or "orders_list.get.py"
                    file_stem = file_path.stem  # filename without extension

                    # Default values
                    endpoint_path = file_stem
                    method_from_filename = None

                    # Check for method in filename (e.g., "user.post.py" -> path="user", method="POST")
                    if "." in file_stem:
                        parts = file_stem.split(".")
                        if len(parts) >= 2 and parts[-1].lower() in [
                            "get",
                            "post",
                            "put",
                            "delete",
                            "patch",
                        ]:
                            endpoint_path = ".".join(parts[:-1])
                            method_from_filename = parts[-1].upper()

                    # Extract relative path for endpoint
                    rel_path = file_path.relative_to(endpoints_dir)
                    endpoint_rel_path = str(rel_path.parent / endpoint_path).replace(
                        "\\", "/"
                    )
                    if endpoint_rel_path == ".":
                        endpoint_rel_path = endpoint_path

                    # Read file content
                    try:
                        with open(file_path, "r") as f:
                            content = f.read()
                    except IOError as io_error:
                        logger.error(f"Error reading file {file_path}: {str(io_error)}")
                        continue  # Skip this file if there's an error reading it

                    # Extract HTTP method from code
                    method_from_code = (
                        ProjectAnalysisService._extract_method_from_content(content)
                    )

                    # Use method from filename if available, otherwise from code
                    method = method_from_filename or method_from_code

                    # Extract function name and parameters
                    function_info = ProjectAnalysisService._extract_function_info(
                        content
                    )

                    # Extract route path from the decorator if available
                    route_path = ProjectAnalysisService._extract_route_path(content)

                    # If route_path starts with /, remove the leading slash for consistency
                    if route_path and route_path.startswith("/"):
                        route_path = route_path[1:]

                    # Use explicit route path if available, otherwise use relative file path
                    final_path = route_path or endpoint_rel_path

                    # Extract return type and docstring for better documentation
                    return_type = ProjectAnalysisService._extract_return_type(content)
                    docstring = ProjectAnalysisService._extract_docstring(content)

                    # Extract dependencies and models used
                    dependencies = ProjectAnalysisService._extract_dependencies(content)
                    models_used = ProjectAnalysisService._extract_models_used(content)

                    # Extract tags if available
                    tags = ProjectAnalysisService._extract_tags(content)

                    # Analyze CRUD operations
                    crud_ops = ProjectAnalysisService._analyze_crud_operations(
                        content, method
                    )

                    # Build comprehensive endpoint info
                    endpoint_info = {
                        "path": final_path,
                        "method": method,
                        "function_name": function_info.get("name"),
                        "parameters": function_info.get("parameters", []),
                        "return_type": return_type,
                        "summary": docstring.get("summary", ""),
                        "description": docstring.get("description", ""),
                        "dependencies": dependencies,
                        "models_used": models_used,
                        "tags": tags,
                        "file": str(file_path.relative_to(endpoints_dir)),
                        "crud_operations": crud_ops,
                    }

                    logger.info(f"Found endpoint: {method} /{final_path}")
                    endpoints.append(endpoint_info)

        logger.info(f"Found {len(endpoints)} endpoints in total")
        return endpoints

    @staticmethod
    def _extract_route_path(content: str) -> Optional[str]:
        """
        Extract the route path from FastAPI route decorators.

        Args:
            content (str): The FastAPI endpoint code

        Returns:
            Optional[str]: The route path if found, None otherwise
        """
        # Patterns for route decorators with path
        patterns = [
            r'@router\.(?:get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
            r'@app\.(?:get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1)

        return None

    @staticmethod
    def _extract_return_type(content: str) -> Optional[str]:
        """
        Extract the return type annotation from the endpoint function.

        Args:
            content (str): The FastAPI endpoint code

        Returns:
            Optional[str]: The return type if found, None otherwise
        """
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.returns:
                    if isinstance(node.returns, ast.Name):
                        return node.returns.id
                    elif isinstance(node.returns, ast.Subscript):
                        # Handle generic types like List[str], Dict[str, Any], etc.
                        if isinstance(node.returns.value, ast.Name):
                            return_type = node.returns.value.id

                            # Try to extract the type arguments
                            if isinstance(node.returns.slice, ast.Index):
                                if hasattr(node.returns.slice, "value"):
                                    if isinstance(node.returns.slice.value, ast.Name):
                                        return f"{return_type}[{node.returns.slice.value.id}]"

                            return return_type
        except SyntaxError:
            pass

        return None

    @staticmethod
    def _extract_docstring(content: str) -> Dict[str, str]:
        """
        Extract the docstring from the endpoint function.

        Args:
            content (str): The FastAPI endpoint code

        Returns:
            Dict[str, str]: Dictionary with summary and description
        """
        result = {"summary": "", "description": ""}

        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and ast.get_docstring(node):
                    docstring = ast.get_docstring(node)
                    lines = docstring.split("\n")

                    # First line is summary, rest is description
                    if lines:
                        result["summary"] = lines[0].strip()
                        if len(lines) > 1:
                            result["description"] = "\n".join(lines[1:]).strip()

                    break
        except SyntaxError:
            pass

        return result

    @staticmethod
    def _extract_dependencies(content: str) -> List[str]:
        """
        Extract FastAPI dependencies used in the endpoint.

        Args:
            content (str): The FastAPI endpoint code

        Returns:
            List[str]: List of dependency names
        """
        dependencies = []

        # Look for Depends() calls
        pattern = r"Depends\s*\(\s*(\w+)"
        for match in re.finditer(pattern, content):
            dependencies.append(match.group(1))

        return dependencies

    @staticmethod
    def _extract_models_used(content: str) -> List[str]:
        """
        Extract data models used in the endpoint.

        Args:
            content (str): The FastAPI endpoint code

        Returns:
            List[str]: List of model names
        """
        models = set()

        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                # Look for function parameters with type annotations
                if isinstance(node, ast.FunctionDef):
                    for arg in node.args.args:
                        if arg.annotation and isinstance(arg.annotation, ast.Name):
                            # Skip common non-model types
                            if arg.annotation.id not in [
                                "str",
                                "int",
                                "float",
                                "bool",
                                "dict",
                                "list",
                                "Any",
                                "Session",
                            ]:
                                models.add(arg.annotation.id)

                # Look for model imports
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module
                    and "models" in node.module
                ):
                    for name in node.names:
                        models.add(name.name)
        except SyntaxError:
            pass

        return list(models)

    @staticmethod
    def _extract_tags(content: str) -> List[str]:
        """
        Extract tags from the FastAPI endpoint decorator.

        Args:
            content (str): The FastAPI endpoint code

        Returns:
            List[str]: List of tags
        """
        tags = []

        # Look for tags parameter in route decorator
        pattern = r'tags\s*=\s*\[\s*[\'"]([^\'"]+)[\'"]'
        for match in re.finditer(pattern, content):
            tags.append(match.group(1))

        return tags

    @staticmethod
    def _analyze_crud_operations(
        content: str, method: Optional[str]
    ) -> Dict[str, bool]:
        """
        Analyze the endpoint code to identify CRUD operations.

        Args:
            content (str): The FastAPI endpoint code
            method (Optional[str]): The HTTP method of the endpoint

        Returns:
            Dict[str, bool]: Dictionary indicating which CRUD operations are performed
        """
        result = {"create": False, "read": False, "update": False, "delete": False}

        # Simple method-based detection
        if method:
            if method == "POST":
                result["create"] = True
            elif method == "GET":
                result["read"] = True
            elif method == "PUT" or method == "PATCH":
                result["update"] = True
            elif method == "DELETE":
                result["delete"] = True

        # Look for specific patterns in the code
        if "db.add" in content:
            result["create"] = True

        if "db.query" in content or "filter" in content:
            result["read"] = True

        if "update" in content.lower() or "set" in content and "=" in content:
            result["update"] = True

        if "delete" in content.lower() or "remove" in content.lower():
            result["delete"] = True

        return result

    @staticmethod
    def _analyze_models(models_dir: Path) -> List[Dict[str, Any]]:
        """
        Analyze model files in the project to extract database model information.

        This improved method handles various SQLAlchemy patterns and model structures.

        Args:
            models_dir (Path): Directory path containing database model files

        Returns:
            List[Dict[str, Any]]: List of model dictionaries with detailed information
        """
        models = []

        # Add detailed logging
        logger.info(f"Analyzing models directory: {models_dir}")

        # Walk through the models directory
        for root, _, files in os.walk(models_dir):
            for file in files:
                if file.endswith(".py") and file != "__init__.py":
                    file_path = Path(root) / file
                    logger.info(f"Examining potential model file: {file_path}")

                    # Read file content
                    try:
                        with open(file_path, "r") as f:
                            content = f.read()
                    except IOError as io_error:
                        logger.error(f"Error reading file {file_path}: {str(io_error)}")
                        continue  # Skip this file if there's an error reading it

                    # First try simple class name extraction to ensure we don't miss anything
                    class_names = ProjectAnalysisService._extract_class_names(content)

                    # Check for SQLAlchemy imports to determine if this is likely a model file
                    is_model_file = (
                        "sqlalchemy" in content
                        or "Column" in content
                        or "Base" in content
                    )

                    # Add all classes from possible model files to ensure we don't miss any
                    if is_model_file:
                        for class_name in class_names:
                            logger.info(
                                f"Found potential model class: {class_name} in {file}"
                            )
                            models.append(
                                {
                                    "name": class_name,
                                    "file": file,
                                    "table_name": class_name.lower()
                                    + "s",  # Default convention
                                    "fields": [],  # We'll parse fields separately if needed
                                }
                            )

                    # Try to use AST for more accurate model detection
                    try:
                        tree = ast.parse(content)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.ClassDef):
                                class_name = node.name

                                # Check if this class inherits from Base or another SQLAlchemy base
                                # or if it's already in our models list from above
                                is_model = False
                                for base in node.bases:
                                    if isinstance(base, ast.Name) and base.id in [
                                        "Base",
                                        "Model",
                                        "db.Model",
                                    ]:
                                        is_model = True
                                        break

                                # If this isn't a model by inheritance, check for tell-tale SQLAlchemy signs
                                if not is_model:
                                    # Check if class body has Column definitions or __tablename__
                                    for item in node.body:
                                        if (
                                            isinstance(item, ast.Assign)
                                            and isinstance(item.value, ast.Call)
                                            and getattr(item.value.func, "id", "")
                                            == "Column"
                                        ):
                                            is_model = True
                                            break

                                        if (
                                            isinstance(item, ast.Assign)
                                            and len(item.targets) == 1
                                            and isinstance(item.targets[0], ast.Name)
                                            and item.targets[0].id == "__tablename__"
                                        ):
                                            is_model = True
                                            break

                                # If we've identified this as a model
                                if is_model:
                                    # Check if we already added this class
                                    already_added = any(
                                        m["name"] == class_name and m["file"] == file
                                        for m in models
                                    )

                                    if already_added:
                                        # Update the existing entry with more details
                                        for model in models:
                                            if (
                                                model["name"] == class_name
                                                and model["file"] == file
                                            ):
                                                # Extract fields using ast
                                                fields = []
                                                table_name = None

                                                # Look for __tablename__ attribute and Column definitions
                                                for class_item in node.body:
                                                    # Check for __tablename__ assignment
                                                    if (
                                                        isinstance(
                                                            class_item, ast.Assign
                                                        )
                                                        and len(class_item.targets) == 1
                                                        and isinstance(
                                                            class_item.targets[0],
                                                            ast.Name,
                                                        )
                                                        and class_item.targets[0].id
                                                        == "__tablename__"
                                                    ):

                                                        if isinstance(
                                                            class_item.value, ast.Str
                                                        ):
                                                            table_name = (
                                                                class_item.value.s
                                                            )

                                                    # Look for field assignments with Column
                                                    if (
                                                        isinstance(
                                                            class_item, ast.Assign
                                                        )
                                                        and len(class_item.targets) == 1
                                                        and isinstance(
                                                            class_item.targets[0],
                                                            ast.Name,
                                                        )
                                                    ):

                                                        field_name = class_item.targets[
                                                            0
                                                        ].id

                                                        # Check if it's a Column definition
                                                        is_column = False
                                                        if (
                                                            isinstance(
                                                                class_item.value,
                                                                ast.Call,
                                                            )
                                                            and isinstance(
                                                                class_item.value.func,
                                                                ast.Name,
                                                            )
                                                            and class_item.value.func.id
                                                            == "Column"
                                                        ):
                                                            is_column = True

                                                        if is_column:
                                                            fields.append(field_name)

                                                # Update the model with extra info
                                                if table_name:
                                                    model["table_name"] = table_name
                                                if fields:
                                                    model["fields"] = fields

                                    else:
                                        # Add as a new model
                                        logger.info(
                                            f"Found SQLAlchemy model via AST: {class_name} in {file}"
                                        )
                                        models.append(
                                            {
                                                "name": class_name,
                                                "file": file,
                                                "table_name": class_name.lower()
                                                + "s",  # Default convention
                                                "fields": [],  # We can fill this later if needed
                                            }
                                        )

                    except SyntaxError as e:
                        logger.error(f"Syntax error parsing {file_path}: {str(e)}")
                        # We already added models from simple class extraction, so no need for fallback

        logger.info(
            f"Found a total of {len(models)} models: {[m['name'] for m in models]}"
        )
        return models

    @staticmethod
    def _analyze_schemas(schemas_dir: Path) -> List[Dict[str, str]]:
        """
        Analyze schema files in the project to extract Pydantic schema information.

        This method recursively traverses the specified directory to find Python files
        that contain Pydantic schema class definitions. It skips __init__.py files and
        extracts class names from each file.

        Args:
            schemas_dir (Path): Directory path containing Pydantic schema files

        Returns:
            List[Dict[str, str]]: List of schema dictionaries, each containing:
                - name: Schema class name
                - file: Source file name
        """
        schemas = []

        # Walk through the schemas directory
        for root, _, files in os.walk(schemas_dir):
            for file in files:
                if file.endswith(".py") and file != "__init__.py":
                    file_path = Path(root) / file

                    # Read file content
                    try:
                        with open(file_path, "r") as f:
                            content = f.read()
                    except IOError as io_error:
                        logger.error(f"Error reading file {file_path}: {str(io_error)}")
                        continue  # Skip this file if there's an error reading it

                    # Extract class names
                    class_names = ProjectAnalysisService._extract_class_names(content)

                    for class_name in class_names:
                        schemas.append({"name": class_name, "file": file})

        return schemas

    @staticmethod
    def _analyze_helpers(helpers_dir: Path) -> List[Dict[str, Any]]:
        """
        Analyze helper files in the project to extract helper function information.

        This method recursively traverses the specified directory to find Python files
        that contain helper functions. It extracts function names and parameters.

        Args:
            helpers_dir (Path): Directory path containing helper function files

        Returns:
            List[Dict[str, Any]]: List of helper dictionaries, each containing:
                - name: Function name
                - file: Source file name
                - parameters: List of parameter names
        """
        helpers = []

        # Walk through the helpers directory
        for root, _, files in os.walk(helpers_dir):
            for file in files:
                if file.endswith(".py") and file != "__init__.py":
                    file_path = Path(root) / file

                    # Read file content
                    try:
                        with open(file_path, "r") as f:
                            content = f.read()
                    except IOError as io_error:
                        logger.error(f"Error reading file {file_path}: {str(io_error)}")
                        continue  # Skip this file if there's an error reading it

                    # Extract function info
                    try:
                        tree = ast.parse(content)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.FunctionDef):
                                params = [
                                    arg.arg
                                    for arg in node.args.args
                                    if arg.arg != "self"
                                ]
                                helpers.append(
                                    {
                                        "name": node.name,
                                        "file": file,
                                        "parameters": params,
                                    }
                                )
                    except SyntaxError as e:
                        logger.error(f"Syntax error parsing {file}: {str(e)}")

        return helpers

    @staticmethod
    def _extract_method_from_content(content: str) -> Optional[str]:
        """
        Extract HTTP method from file content using regular expressions.

        This method searches for FastAPI route decorators in the provided code
        and extracts the HTTP method (GET, POST, PUT, DELETE, PATCH) being used.
        It supports both router-style and app-style route decorators.

        Args:
            content (str): The FastAPI code content to analyze

        Returns:
            Optional[str]: The detected HTTP method in uppercase (e.g., "GET", "POST"),
                          or None if no method could be detected
        """
        # Common patterns for FastAPI route decorators
        method_patterns = [
            r"@router\.get\s*\(",
            r"@router\.post\s*\(",
            r"@router\.put\s*\(",
            r"@router\.delete\s*\(",
            r"@router\.patch\s*\(",
            r"@app\.get\s*\(",
            r"@app\.post\s*\(",
            r"@app\.put\s*\(",
            r"@app\.delete\s*\(",
            r"@app\.patch\s*\(",
        ]

        for pattern in method_patterns:
            match = re.search(pattern, content)
            if match:
                # Extract the method from the pattern (e.g., 'get' from '@router.get')
                method = match.group(0).split(".")[1].split("(")[0].strip().upper()
                return method

        return None

    @staticmethod
    def _extract_function_info(content: str) -> Dict[str, Any]:
        """
        Extract function name and parameters from Python code using AST.

        This method parses the provided code content using Python's Abstract Syntax Tree (AST)
        to reliably extract the first function definition along with its parameter names.
        It excludes 'self' from the parameter list to focus on API endpoint parameters.

        Args:
            content (str): Python code content to analyze

        Returns:
            Dict[str, Any]: Dictionary containing:
                - name: Function name (or None if no function found)
                - parameters: List of parameter names (excluding 'self')
        """
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            logger.error(f"Syntax error during parsing: {str(e)}")
            return {"name": None, "parameters": []}

        # Find the first function definition in the AST
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Exclude 'self' parameter if present
                params = [arg.arg for arg in node.args.args if arg.arg != "self"]
                return {"name": node.name, "parameters": params}

        return {"name": None, "parameters": []}

    @staticmethod
    def _extract_class_names(content: str) -> List[str]:
        """
        Extract class names from Python code content using regular expressions.

        This method searches for class definitions in the provided Python code
        and extracts the class names using a regex pattern that matches standard
        Python class naming conventions.

        Args:
            content (str): Python code content to analyze

        Returns:
            List[str]: List of found class names
        """
        # Pattern to match class definitions
        class_pattern = r"class\s+([a-zA-Z_][a-zA-Z0-9_]*)"

        class_names = []
        for match in re.finditer(class_pattern, content):
            class_names.append(match.group(1))

        return class_names

    @staticmethod
    def _generate_summary(analysis: Dict[str, Any]) -> str:
        """
        Generate a human-readable summary of the project analysis results.

        This method creates a formatted text summary of the endpoints, models,
        schemas, and helpers found in the project. It limits the output to the
        first 5 items in each category for brevity, with a count of additional items.

        Args:
            analysis (Dict[str, Any]): Project analysis data containing:
                - endpoints: List of endpoint dictionaries
                - models: List of model dictionaries
                - schemas: List of schema dictionaries
                - helpers: List of helper dictionaries

        Returns:
            str: Formatted summary text with information about project components
        """
        summary = []

        # Add endpoints summary
        if analysis.get("endpoints"):
            endpoints_summary = (
                f"The project has {len(analysis['endpoints'])} endpoints:"
            )
            for endpoint in analysis["endpoints"][:5]:
                method = endpoint.get("method", "UNKNOWN")
                path = endpoint.get("path", "")
                endpoints_summary += f"\n- {method} /{path}"
            if len(analysis["endpoints"]) > 5:
                endpoints_summary += (
                    f"\n- ... and {len(analysis['endpoints']) - 5} more"
                )
            summary.append(endpoints_summary)

        # Add models summary
        if analysis.get("models"):
            models_summary = f"The project has {len(analysis['models'])} models:"
            for model in analysis["models"][:5]:
                models_summary += f"\n- {model.get('name')}"
            if len(analysis["models"]) > 5:
                models_summary += f"\n- ... and {len(analysis['models']) - 5} more"
            summary.append(models_summary)

        # Add schemas summary
        if analysis.get("schemas"):
            schemas_summary = f"The project has {len(analysis['schemas'])} schemas:"
            for schema in analysis["schemas"][:5]:
                schemas_summary += f"\n- {schema.get('name')}"
            if len(analysis["schemas"]) > 5:
                schemas_summary += f"\n- ... and {len(analysis['schemas']) - 5} more"
            summary.append(schemas_summary)

        # Add helpers summary
        if analysis.get("helpers"):
            helpers_summary = (
                f"The project has {len(analysis['helpers'])} helper functions:"
            )
            for helper in analysis["helpers"][:5]:
                helpers_summary += f"\n- {helper.get('name')}"
            if len(analysis["helpers"]) > 5:
                helpers_summary += f"\n- ... and {len(analysis['helpers']) - 5} more"
            summary.append(helpers_summary)

        return "\n\n".join(summary)
