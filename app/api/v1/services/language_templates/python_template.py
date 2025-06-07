import asyncio
import configparser
import importlib
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from alembic.config import Config
from app.api.v1.services.git_service import GitService
from app.api.v1.services.langchain_service import LangchainService
from app.api.v1.services.language_templates.language_template import LanguageTemplate

logger = logging.getLogger(__name__)


class PythonTemplate(LanguageTemplate):
    """Python-specific implementation of language template"""

    # Enable Git commits for generated code files
    git_enabled = True

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

    def extract_entity_from_prompt(self, prompt: str) -> str:
        """
        Improved extraction of entity name(s) from a natural language prompt for Python code generation.
        Handles lowercase, multi-word entities, and more flexible prompt structures.
        Uses spaCy for noun phrase extraction if available, otherwise falls back to regex.

        Args:
            prompt (str): The natural language prompt

        Returns:
            str: The extracted entity name, or an empty string if not found"""
        try:
            import spacy

            nlp = spacy.load("en_core_web_sm")
            doc = nlp(prompt)
            # Extract the longest noun chunk (noun phrase)
            noun_chunks = list(doc.noun_chunks)
            if noun_chunks:
                # Return the longest noun chunk (most likely the entity)
                entity = max(noun_chunks, key=lambda nc: len(nc.text)).text.strip()
                # Remove trailing punctuation
                entity = re.sub(r"[.?!,;:]$", "", entity)
                return entity
        except Exception:
            pass  # spaCy not installed or model not available, fallback to regex

        # Lowercase prompt for matching, but keep original for extraction
        prompt_lc = prompt.lower()
        original = prompt

        # Try to extract after common verbs (manage, create, add, delete, update, etc.)
        verb_pattern = r"(?:manage|create|add|delete|update|edit|remove|list|get|set|find|generate|build|make|fetch|retrieve|handle|process|modify|view|show|display|read|write|save|store|archive|export|import|sync|synchronize|search|filter|sort|assign|unassign|link|unlink|associate|dissociate|connect|disconnect|enable|disable|activate|deactivate|approve|reject|submit|cancel|complete|start|stop|pause|resume|schedule|unschedule|book|unbook|order|purchase|sell|buy|ship|deliver|return|refund|pay|charge|bill|invoice|quote|estimate|track|monitor|log|audit|report|notify|alert|remind|invite|register|sign up|sign in|login|logout|authenticate|authorize|verify|validate|confirm|decline|block|unblock|ban|unban|mute|unmute|follow|unfollow|like|unlike|comment|reply|share|post|publish|unpublish|draft|undraft|pin|unpin|favorite|unfavorite|star|unstar|rate|review|score|vote|upvote|downvote|recommend|suggest|request|offer|accept|decline|join|leave|enter|exit|open|close|lock|unlock)\s+(?:an?\s+|the\s+|all\s+|multiple\s+|many\s+|a list of\s+|)"  # verb + optional article/quantifier
        # Try to match multi-word entities (e.g., 'orders of product', 'user profile', 'order item')
        entity_pattern = verb_pattern + r"([a-zA-Z0-9_\- ]+(?: of [a-zA-Z0-9_\- ]+)*)"
        match = re.search(entity_pattern, prompt_lc)
        if match:
            # Extract the matched entity phrase from the original prompt (preserve casing)
            start = match.start(1)
            end = match.end(1)
            entity = original[start:end].strip()
            # Remove trailing punctuation
            entity = re.sub(r"[.?!,;:]$", "", entity)
            return entity

        # Fallback: look for the last noun-like word or phrase (e.g., after 'of')
        fallback_match = re.search(r"([a-zA-Z0-9_\- ]+)$", prompt.strip())
        if fallback_match:
            entity = fallback_match.group(1).strip()
            entity = re.sub(r"[.?!,;:]$", "", entity)
            return entity

        # Fallback: look for the first capitalized word (legacy behavior)
        cap_match = re.search(r"([A-Z][a-zA-Z0-9_]*)", original)
        if cap_match:
            return cap_match.group(1)

        return ""

    def get_file_extension(self) -> str:
        """
        Get the standard file extension for Python files.

        Returns:
            str: File extension for Python ("py")
        """
        return "py"

    def get_required_components(self) -> List[str]:
        """
        Get components required for Python FastAPI applications.

        Returns:
            List[str]: List of required Python component types
        """
        return ["endpoint", "model", "schema", "migration", "helpers"]

    def needs_schema(self, code: str) -> bool:
        """
        Check if the Python endpoint code references schema-related components.

        Args:
            code (str): The Python code to analyze

        Returns:
            bool: True if the code references schema components
        """
        if not code or not isinstance(code, str):
            logger.warning("No valid endpoint code provided for schema detection")
            return False

        schema_patterns = [
            r"from\s+schemas\s+import\s+\w+",  # e.g., from schemas import UserSchema
            r"from\s+schemas\.(\w+)\s+import\s+\w+",  # e.g., from schemas.user import UserSchema
            r"\w+Schema\s*\(",  # e.g., UserSchema(...)
            r"\w+Schema\s*:",  # e.g., user: UserSchema
            r"schema\s*=\s*\w+Schema",  # e.g., schema = UserSchema
            r"validate_with_\w+Schema",  # e.g., validate_with_UserSchema
        ]

        logger.debug(
            f"Checking for schema references in endpoint code:\n{code[:1000]}..."
        )  # Log first 1000 chars
        for pattern in schema_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                logger.info(f"Schema dependency detected with pattern: {pattern}")
                return True
        logger.debug("No schema dependencies detected in endpoint code")
        return False

    def needs_helpers(self, code: str) -> bool:
        """
        Check if the Python endpoint code references helper functions.

        Args:
            code (str): The Python code to analyze

        Returns:
            bool: True if the code references helper functions
        """
        if not code or not isinstance(code, str):
            logger.warning("No valid endpoint code provided for helpers detection")
            return False

        helper_patterns = [
            r"from\s+helpers\s+import\s+\w+",  # e.g., from helpers import user_utils
            r"from\s+helpers\.(\w+)_helpers\s+import\s+\w+",  # e.g., from helpers.user_helpers import validate_user
            r"\w+_helpers\.\w+",  # e.g., user_helpers.validate_user
            r"helper_\w+",  # e.g., helper_validate_user
        ]

        logger.debug(
            f"Checking for helper references in endpoint code:\n{code[:1000]}..."
        )  # Log first 1000 chars
        for pattern in helper_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                logger.info(f"Helper dependency detected with pattern: {pattern}")
                return True
        logger.debug("No helper dependencies detected in endpoint code")
        return False

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

    def get_component_paths(
        self, project_id: str, entity_name: str, **kwargs
    ) -> Dict[str, str]:
        """
        Get file paths for Python components based on project conventions.
        Always uses singular form for component filenames, regardless of endpoint path.

        Args:
            project_id (str): Identifier for the project being modified
            entity_name (str): Name of the entity to generate paths for

        Returns:
            Dict[str, str]: Mapping of component types to their file paths
        """
        snake_case_entity = self._to_snake_case(entity_name)
        # For endpoints, use the endpoint path and method from kwargs if available
        endpoint_path = kwargs.get("endpoint_path", "")
        method = kwargs.get("method", "").lower()
        if endpoint_path and method:
            # Extract the last segment of the path for the filename
            path_segments = endpoint_path.strip("/").split("/")
            last_segment = path_segments[-1] if path_segments else endpoint_path
            endpoint_file = f"endpoints/{last_segment}.{method}.py"
            api_docs_file = f"docs/{last_segment}.{method}.md"
        else:
            # Fallback to entity-based naming if endpoint path is not provided
            endpoint_file = f"endpoints/{snake_case_entity}.py"
            api_docs_file = f"docs/{snake_case_entity}.md"

        return {
            "endpoint": endpoint_file,
            "model": f"models/{snake_case_entity}.py",
            "schema": f"schemas/{snake_case_entity}.py",
            "migration": f"alembic/versions/create_{snake_case_entity}_table.py",
            "helpers": f"helpers/{snake_case_entity}_helpers.py",
            "api_docs": api_docs_file,
        }

    def extract_entity_from_code(self, code: str) -> Optional[str]:
        """
        Extract entity name from Python code using regex patterns.

        Args:
            code (str): The Python code to analyze

        Returns:
            Optional[str]: Extracted entity name or None if no entity could be identified
        """
        if not code or not isinstance(code, str):
            return None
        try:
            # Pattern for model imports (absolute imports)
            model_import = re.search(r"from\s+.*models?\s+import\s+(\w+)", code)
            if model_import:
                return model_import.group(1)
            # Pattern for model imports (relative/specific imports)
            model_import_specific = re.search(
                r"from\s+models\.(\w+)\s+import\s+(\w+)", code
            )
            if model_import_specific:
                return model_import_specific.group(2)
            # Pattern for db queries
            db_query = re.search(r"db\.query\((\w+)\)", code)
            if db_query:
                return db_query.group(1)
            # Pattern for schema imports (specific path)
            schema_import = re.search(
                r"from\s+schemas\.(\w+)\s+import\s+(\w+)Schema", code
            )
            if schema_import:
                return schema_import.group(2)
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
            # Look for helper function imports that might contain entity names
            helper_import = re.search(r"from\s+helpers\.(\w+)_helpers\s+import", code)
            if helper_import:
                # Convert snake_case to PascalCase if needed
                entity = helper_import.group(1)
                return "".join(word.capitalize() for word in entity.split("_"))
            # Look for route paths that might indicate the entity
            route_path = re.search(r'@router\.\w+\([\'"]/?(\w+)[\'"]', code)
            if route_path:
                # Convert plural to singular if needed
                entity = route_path.group(1)
                if entity.endswith("s"):
                    entity = entity[:-1]
                return entity.capitalize()
            # Look for common CRUD operation functions
            crud_function = re.search(
                r"def\s+(?:get|create|update|delete|find)_?(\w+)", code
            )
            if crud_function:
                entity = crud_function.group(1)
                if entity.endswith("s"):
                    entity = entity[:-1]
                return entity.capitalize()
            # Look for FastAPI path operations
            fastapi_path = re.search(r"@app\.\w+\([\'\"]/(\w+)", code)
            if fastapi_path:
                entity = fastapi_path.group(1)
                if entity.endswith("s"):
                    entity = entity[:-1]
                return entity.capitalize()
            # Look for SQLAlchemy table definitions
            sqlalchemy_table = re.search(r"Table\([\'\"]\w*(\w+)s?[\'\"]\s*,", code)
            if sqlalchemy_table:
                entity = sqlalchemy_table.group(1)
                return entity.capitalize()
            # Last resort: look for patterns in function parameters
            function_params = re.search(r"def\s+\w+\([^)]*?(\w+)_id", code)
            if function_params:
                return function_params.group(1).capitalize()
            return None
        except Exception as e:
            logger.error(f"Error extracting entity from code: {str(e)}")
            # Log the exception but don't crash
            return None

    async def generate_component(
        self,
        component_type: str,
        project_id: str,
        entity_name: str,
        entity_description: str,
        streaming_callback=None,
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

        # Enhanced context reading for endpoint components
        related_endpoints = []
        if component_type == "endpoint":
            related_endpoints = await self._read_related_endpoints(
                project_id, entity_name, **kwargs
            )  # Prepare template variables
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
            # Pass current file content for context-aware updates
            "current_code": kwargs.get("current_code", None),
            # Enhanced context: related endpoint files
            "related_endpoints": related_endpoints,
            # Enhanced context: similar endpoint patterns
            "similar_endpoints": kwargs.get("similar_endpoints", {}),
        }  # Generate code using PromptManager template with streaming support
        if streaming_callback:
            result = await LangchainService.generate_code_with_template_streaming(
                template_name=template_name,
                language="python",
                streaming_callback=streaming_callback,
                **template_vars,
            )
        else:
            result = await LangchainService.generate_code_with_template(
                template_name=template_name, language="python", **template_vars
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

    async def generate_dockerfile(
        self, project_id: str, entity_name: str, streaming_callback=None
    ) -> str:
        """
        Generate a Dockerfile for Python FastAPI application.

        Args:
            project_id (str): The project ID
            entity_name (str): The name of the entity

        Returns:
            str: Dockerfile content
        """
        try:  # Use the prompt template via LangchainService with streaming support
            if streaming_callback:
                result = await LangchainService.generate_code_with_template_streaming(
                    template_name="dockerfile",
                    language="python",
                    streaming_callback=streaming_callback,
                    project_id=project_id,
                    entity_name=entity_name,
                )
            else:
                result = await LangchainService.generate_code_with_template(
                    template_name="dockerfile",
                    language="python",
                    project_id=project_id,
                    entity_name=entity_name,
                )

            return result["generated_code"]
        except Exception as e:
            logger.error(f"Error generating Dockerfile: {str(e)}")
            # Fallback to a default Dockerfile if generation fails
            return """FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
# Run migrations if applicable
RUN alembic upgrade head || true
# Start the server
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""

    def get_commit_strategy(self) -> Dict[str, Any]:
        """
        Get strategy for committing Python components to version control.

        Returns:
            Dict[str, Any]: Commit strategy with component order and message templates
        """
        return {
            "components": [
                "model",
                "schema",
                "migration",
                "helpers",
                "endpoint",
                "dockerfile",
                "api_docs",
                "database",
            ],
            "commit_order": [
                "model",
                "schema",
                "migration",
                "helpers",
                "endpoint",
                "dockerfile",
                "api_docs",
                "database",
            ],
            "commit_messages": {
                "endpoint": "Add {method} endpoint for {endpoint_path}",
                "model": "Add {entity_name} model",
                "schema": "Add {entity_name} schema",
                "migration": "Add migration for {entity_name} model",
                "helpers": "Add helper functions for {entity_name}",
                "dockerfile": "Add Dockerfile for {entity_name}",
                "api_docs": "Add API documentation for {entity_name}",
                "database": "Add SQLite database for {entity_name}",
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

    async def run_migrations(self, project_dir: Path) -> dict:
        """
        Runs simplified database migrations by scanning model files and creating corresponding tables in a SQLite database.
        This method inspects Python model files in the project's 'models' directory, extracts table and column definitions,
        and generates SQL statements to create any missing tables in the project's SQLite database. It also commits the updated
        database file to Git if new tables are created.
        Args:
            project_dir (Path): The root directory of the project, containing the 'models' and 'storage/db' subdirectories.
        Returns:
            dict: A dictionary containing the migration results with the following keys:
                - "success" (bool): Whether the migration process completed successfully.
                - "database_path" (str or None): The path to the SQLite database file.
                - "message" (str): A summary message about the migration process.
                - "tables_created" (list): A list of table names that were created.
                - "git_commit" (dict or None): Information about the Git commit, if applicable.
        """
        logger.info(f"Running simplified migrations in {project_dir}")
        result = {
            "success": False,
            "database_path": None,
            "message": "",
            "tables_created": [],
            "git_commit": None,
        }

        # Set up directories with proper absolute paths
        storage_dir = project_dir / "storage" / "db"
        storage_dir.mkdir(exist_ok=True, parents=True)
        sqlite_path = storage_dir / "db.sqlite"
        logger.info(f"Storage directory: {storage_dir}")
        logger.info(f"SQLite path: {sqlite_path}")

        # Make sure database connection works
        try:
            conn = sqlite3.connect(str(sqlite_path))
            cursor = conn.cursor()

            # Get a list of existing tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            existing_tables = [table[0] for table in cursor.fetchall()]
            logger.info(f"Existing tables: {existing_tables}")

            # Now, scan the models directory to find new models
            models_dir = project_dir / "models"
            if models_dir.exists():
                model_files = list(models_dir.glob("*.py"))
                logger.info(f"Found {len(model_files)} model files")

                tables_created = []

                # For each model file, try to extract the table definition
                for model_file in model_files:
                    model_name = model_file.stem
                    logger.info(f"Processing model: {model_name}")

                    # Read the model file content
                    model_content = model_file.read_text()

                    # Try to extract table name from the model
                    table_name_match = re.search(
                        r"__tablename__\s*=\s*['\"]([^'\"]+)['\"]", model_content
                    )
                    if table_name_match:
                        table_name = table_name_match.group(1)
                    else:
                        # If no explicit table name, use the snake_case model name + 's'
                        snake_case = self._to_snake_case(model_name)
                        table_name = f"{snake_case}s"

                    # Check if this table already exists
                    if table_name in existing_tables:
                        logger.info(f"Table {table_name} already exists, skipping")
                        continue

                    # Try to extract the column definitions
                    try:
                        # Analyze the model content to extract column definitions
                        columns = []
                        column_matches = re.finditer(
                            r"(\w+)\s*=\s*Column\(([^)]+)\)", model_content
                        )

                        for match in column_matches:
                            column_name = match.group(1)
                            column_def = match.group(2)
                            columns.append((column_name, column_def))

                        # Generate a CREATE TABLE statement
                        if columns:
                            create_table_sql = (
                                f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
                            )

                            sql_columns = []
                            for col_name, col_def in columns:
                                # Simplify SQLAlchemy type definitions to basic SQLite types
                                sqlite_type = "TEXT"  # Default type

                                if "Integer" in col_def:
                                    sqlite_type = "INTEGER"
                                elif "Float" in col_def:
                                    sqlite_type = "REAL"
                                elif "Boolean" in col_def:
                                    sqlite_type = "BOOLEAN"
                                elif "DateTime" in col_def:
                                    sqlite_type = "TIMESTAMP"

                                # Check for primary key
                                is_primary = (
                                    "primary_key=True" in col_def
                                    or "primary_key = True" in col_def
                                )
                                primary_key = "PRIMARY KEY" if is_primary else ""

                                # Check for nullable
                                is_nullable = not (
                                    "nullable=False" in col_def
                                    or "nullable = False" in col_def
                                )
                                nullable = "" if is_nullable else "NOT NULL"

                                # Column definition
                                sql_col = f"    {col_name} {sqlite_type} {primary_key} {nullable}".strip()
                                sql_columns.append(sql_col)

                            create_table_sql += ",\n".join(sql_columns)
                            create_table_sql += "\n);"

                            logger.info(f"Executing SQL: {create_table_sql}")

                            # Execute the CREATE TABLE statement
                            cursor.execute(create_table_sql)
                            conn.commit()

                            tables_created.append(table_name)
                            logger.info(f"Created table: {table_name}")

                    except Exception as e:
                        logger.error(
                            f"Error creating table from model {model_name}: {str(e)}"
                        )

                # Update result with tables created
                result["tables_created"] = tables_created
                if tables_created:
                    result["message"] = (
                        f"Created {len(tables_created)} new tables: {', '.join(tables_created)}"
                    )
                else:
                    result["message"] = "No new tables needed to be created."

            conn.close()
            result["success"] = True
            result["database_path"] = str(sqlite_path)
            # If we successfully updated the database, commit it to Git
            if result["success"] and sqlite_path.exists():
                try:  # Get the project_id from the project_dir path
                    project_id = project_dir.name

                    # Read the database as binary data
                    with open(sqlite_path, "rb") as f:
                        sqlite_data = f.read()

                    relative_path = str(sqlite_path.relative_to(project_dir))
                    commit_message = f"Update SQLite database with new tables - {', '.join(tables_created)}"

                    # Use the GitService to commit the binary file
                    commit_result = await GitService.commit_binary_file_update(
                        project_id=project_id,
                        binary_content=sqlite_data,
                        file_path=relative_path,
                        commit_message=commit_message,
                    )

                    result["git_commit"] = {
                        "success": True,
                        "commit_id": commit_result,
                        "message": commit_message,
                    }

                    logger.info(
                        f"Successfully committed updated database to Git with ID: {commit_result}"
                    )

                except Exception as e:
                    error_msg = f"Error committing database to Git: {str(e)}"
                    logger.error(error_msg)
                    result["git_commit"] = {"success": False, "error": error_msg}

        except Exception as e:
            error_msg = f"Error during migration: {str(e)}"
            logger.error(error_msg)
            result["message"] = error_msg
            return result

        logger.info(f"Migration process completed with success={result['success']}")
        return result

    async def run_migrations_with_logs(self, project_dir: Path, logger) -> dict:
        """
        Runs simplified database migrations while streaming logs to the provided logger.
        This is the same as run_migrations but with real-time log streaming for frontend display.

        Args:
            project_dir (Path): The root directory of the project
            logger: An async logger object to stream logs to the frontend

        Returns:
            dict: Migration results with success status, database path, message, and tables created
        """
        await logger.info(f"Running simplified migrations in {project_dir}")
        result = {
            "success": False,
            "database_path": None,
            "message": "",
            "tables_created": [],
            "git_commit": None,
        }

        # Set up directories with proper absolute paths
        storage_dir = project_dir / "storage" / "db"
        storage_dir.mkdir(exist_ok=True, parents=True)
        sqlite_path = storage_dir / "db.sqlite"
        await logger.info(f"Storage directory: {storage_dir}")
        await logger.info(f"SQLite path: {sqlite_path}")

        # Make sure database connection works
        try:
            conn = sqlite3.connect(str(sqlite_path))
            cursor = conn.cursor()

            await logger.info("Database connection established successfully")

            # Get a list of existing tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            existing_tables = [table[0] for table in cursor.fetchall()]
            await logger.info(
                f"Detected {len(existing_tables)} existing tables in database"
            )

            # Now, scan the models directory to find new models
            models_dir = project_dir / "models"
            if models_dir.exists():
                model_files = list(models_dir.glob("*.py"))
                await logger.info(f"Found {len(model_files)} model files to analyze")

                tables_created = []

                # For each model file, try to extract the table definition
                for model_file in model_files:
                    model_name = model_file.stem
                    await logger.info(f"Analyzing model: {model_name}")

                    # Read the model file content
                    model_content = model_file.read_text()

                    # Add some delay to simulate processing time
                    await asyncio.sleep(0.2)

                    # Try to extract table name from the model
                    table_name_match = re.search(
                        r"__tablename__\s*=\s*['\"]([^'\"]+)['\"]", model_content
                    )
                    if table_name_match:
                        table_name = table_name_match.group(1)
                        await logger.info(
                            f"Found table name '{table_name}' in model definition"
                        )
                    else:
                        # If no explicit table name, use the snake_case model name + 's'
                        snake_case = self._to_snake_case(model_name)
                        table_name = f"{snake_case}s"
                        await logger.info(
                            f"No explicit table name found, using '{table_name}'"
                        )

                    # Check if this table already exists
                    if table_name in existing_tables:
                        await logger.info(
                            f"Table '{table_name}' already exists, skipping"
                        )
                        continue

                    # Try to extract the column definitions
                    try:
                        await logger.info(
                            f"Extracting column definitions for '{table_name}'"
                        )
                        # Analyze the model content to extract column definitions
                        columns = []
                        column_matches = re.finditer(
                            r"(\w+)\s*=\s*Column\(([^)]+)\)", model_content
                        )

                        for match in column_matches:
                            column_name = match.group(1)
                            column_def = match.group(2)
                            columns.append((column_name, column_def))
                            await logger.info(
                                f"Found column: {column_name} ({column_def})"
                            )

                        # Generate a CREATE TABLE statement
                        if columns:
                            await logger.info(
                                f"Generating CREATE TABLE statement for '{table_name}'"
                            )
                            create_table_sql = (
                                f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
                            )

                            sql_columns = []
                            for col_name, col_def in columns:
                                # Simplify SQLAlchemy type definitions to basic SQLite types
                                sqlite_type = "TEXT"  # Default type

                                if "Integer" in col_def:
                                    sqlite_type = "INTEGER"
                                elif "Float" in col_def:
                                    sqlite_type = "REAL"
                                elif "Boolean" in col_def:
                                    sqlite_type = "BOOLEAN"
                                elif "DateTime" in col_def:
                                    sqlite_type = "TIMESTAMP"

                                # Check for primary key
                                is_primary = (
                                    "primary_key=True" in col_def
                                    or "primary_key = True" in col_def
                                )
                                primary_key = "PRIMARY KEY" if is_primary else ""

                                # Check for nullable
                                is_nullable = not (
                                    "nullable=False" in col_def
                                    or "nullable = False" in col_def
                                )
                                nullable = "" if is_nullable else "NOT NULL"

                                # Column definition
                                sql_col = f"    {col_name} {sqlite_type} {primary_key} {nullable}".strip()
                                sql_columns.append(sql_col)

                            create_table_sql += ",\n".join(sql_columns)
                            create_table_sql += "\n);"

                            await logger.info(f"Executing SQL:\n{create_table_sql}")

                            # Execute the CREATE TABLE statement
                            cursor.execute(create_table_sql)
                            conn.commit()

                            tables_created.append(table_name)
                            await logger.info(
                                f"✅ Successfully created table: {table_name}"
                            )

                    except Exception as e:
                        error_msg = (
                            f"Error creating table from model {model_name}: {str(e)}"
                        )
                        await logger.error(error_msg)

                # Update result with tables created
                result["tables_created"] = tables_created
                if tables_created:
                    result["message"] = (
                        f"Created {len(tables_created)} new tables: {', '.join(tables_created)}"
                    )
                    await logger.info(f"Migration summary: {result['message']}")
                else:
                    result["message"] = "No new tables needed to be created."
                    await logger.info(f"Migration summary: {result['message']}")

            conn.close()
            result["success"] = True
            result["database_path"] = str(sqlite_path)

            # If we successfully updated the database, commit it to Git
            if result["success"] and sqlite_path.exists() and result["tables_created"]:
                try:
                    # Get the project_id from the project_dir path
                    project_id = project_dir.name
                    await logger.info(
                        f"Committing changes to Git (project_id: {project_id})"
                    )  # Read the database as binary data
                    with open(sqlite_path, "rb") as f:
                        sqlite_data = f.read()
                    await logger.info(
                        f"Read {len(sqlite_data)} bytes from database file"
                    )

                    relative_path = str(sqlite_path.relative_to(project_dir))
                    commit_message = f"Update SQLite database with new tables - {', '.join(tables_created)}"

                    # Use the GitService to commit the binary file
                    await logger.info(
                        f"Creating Git commit with message: {commit_message}"
                    )
                    commit_result = await GitService.commit_binary_file_update(
                        project_id=project_id,
                        binary_content=sqlite_data,
                        file_path=relative_path,
                        commit_message=commit_message,
                    )

                    result["git_commit"] = {
                        "success": True,
                        "commit_id": commit_result,
                        "message": commit_message,
                    }

                    await logger.info(
                        f"✅ Successfully committed database to Git with ID: {commit_result}"
                    )

                except Exception as e:
                    error_msg = f"Error committing database to Git: {str(e)}"
                    await logger.error(error_msg)
                    result["git_commit"] = {"success": False, "error": error_msg}

        except Exception as e:
            error_msg = f"Error during migration: {str(e)}"
            await logger.error(error_msg)
            result["message"] = error_msg
            return result

        await logger.info(
            f"Migration process completed with success={result['success']}"
        )
        return result

    def _find_latest_migration_id(self, project_dir: Path, versions_dir: Path) -> str:
        """
        Find the latest Alembic migration revision ID in the versions directory.
        Returns the revision ID as a string, or an empty string if none found.
        """
        migration_files = sorted(
            versions_dir.glob("*.py"), key=os.path.getmtime, reverse=True
        )
        for migration_file in migration_files:
            with open(migration_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("revision"):
                        parts = line.split("=")
                        if len(parts) == 2:
                            return parts[1].strip().strip("'\"")
        return ""

    async def generate_migration(self, project_dir: str, entity_name: str) -> dict:
        # Convert string to Path object if needed
        if isinstance(project_dir, str):
            project_dir = Path(project_dir)

        log_path = project_dir / "migration_codegen.log"
        logger = logging.getLogger("migration_codegen")
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        fh.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s:%(name)s:%(message)s")
        )
        if not any(
            isinstance(h, logging.FileHandler) and h.baseFilename == str(log_path)
            for h in logger.handlers
        ):
            logger.addHandler(fh)
        result = {
            "migration_files": [],
            "migration_component": None,
            "migration_status": "unknown",
            "error": None,
        }
        try:
            logger.info(f"Starting migration generation for entity: {entity_name}")
            fh.flush()  # Set up Alembic config with absolute paths
            alembic_dir = project_dir / "alembic"
            versions_dir = alembic_dir / "versions"
            alembic_ini = project_dir / "alembic.ini"

            # Convert to absolute paths to avoid any path confusion
            alembic_dir = alembic_dir.resolve()
            versions_dir = versions_dir.resolve()
            alembic_ini = alembic_ini.resolve()

            versions_dir.mkdir(parents=True, exist_ok=True)
            db_path = (
                project_dir / "storage" / "db" / "db.sqlite"
            ).resolve()  # Ensure alembic.ini exists (copy from template if needed)
            if not alembic_ini.exists():
                template_ini = (
                    Path(__file__).parent.parent.parent.parent.parent.parent
                    / "project_template"
                    / "python"
                    / "alembic.ini"
                )
                if template_ini.exists():
                    shutil.copy(template_ini, alembic_ini)

            # Ensure env.py exists (copy from template if needed)
            env_py_path = alembic_dir / "env.py"
            if not env_py_path.exists():
                template_env = (
                    Path(__file__).parent.parent.parent.parent.parent.parent
                    / "project_template"
                    / "python"
                    / "alembic"
                    / "env.py"
                )
                if template_env.exists():
                    shutil.copy(template_env, env_py_path)

            # Ensure script.py.mako exists (copy from template if needed)
            script_mako_path = alembic_dir / "script.py.mako"
            if not script_mako_path.exists():
                template_script = (
                    Path(__file__).parent.parent.parent.parent.parent.parent
                    / "project_template"
                    / "python"
                    / "alembic"
                    / "script.py.mako"
                )
                if template_script.exists():
                    shutil.copy(template_script, script_mako_path)

            # Ensure core/database.py exists (copy from template if needed)
            core_dir = project_dir / "core"
            core_dir.mkdir(exist_ok=True)
            database_py_path = core_dir / "database.py"
            if not database_py_path.exists():
                template_database = (
                    Path(__file__).parent.parent.parent.parent.parent.parent
                    / "project_template"
                    / "python"
                    / "core"
                    / "database.py"
                )
                if template_database.exists():
                    shutil.copy(template_database, database_py_path)

            # Create core/__init__.py if it doesn't exist
            core_init_path = core_dir / "__init__.py"
            if not core_init_path.exists():
                core_init_path.write_text("")
            # Patch alembic.ini to point to the correct SQLite DB

            config = configparser.ConfigParser()
            config.read(alembic_ini)
            if "alembic" not in config:
                config["alembic"] = {}
            config["alembic"]["sqlalchemy.url"] = f"sqlite:///{db_path}"
            with open(alembic_ini, "w") as f:
                config.write(f)
            # Alembic Config

            alembic_cfg = Config(str(alembic_ini))
            alembic_cfg.set_main_option("script_location", str(alembic_dir))
            alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
            logger.info(f"Using Alembic config: {alembic_ini}")
            fh.flush()
            logger.info(f"Using database path: {db_path}")
            fh.flush()
            logger.info(f"Importing all models from {project_dir / 'models'}")
            fh.flush()

            project_dir_abs = project_dir.resolve()
            if str(project_dir_abs) not in sys.path:
                sys.path.insert(0, str(project_dir_abs))
            models_dir = project_dir / "models"
            if models_dir.exists():
                for file in os.listdir(models_dir):
                    if file.endswith(".py") and not file.startswith("__"):
                        module_name = f"models.{file[:-3]}"
                        try:
                            importlib.import_module(module_name)
                            logger.info(f"Imported model module: {module_name}")
                            fh.flush()
                        except Exception as e:
                            logger.warning(f"Could not import {module_name}: {e}")
                            fh.flush()  # Find latest migration ID
            migration_id = uuid.uuid4().hex[:12]
            migration_msg = f"autogenerated migration for {entity_name or 'project'}"  # Use subprocess to run Alembic commands to avoid terminal conflicts
            logger.info("Running Alembic upgrade head before autogenerate...")
            fh.flush()
            try:  # Run upgrade in subprocess to avoid terminal interaction issues
                upgrade_result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        f"from alembic.config import Config; from alembic import command; "
                        f"cfg = Config({repr(str(alembic_ini))}); cfg.set_main_option('script_location', {repr(str(alembic_dir))}); "
                        f"cfg.set_main_option('sqlalchemy.url', {repr(f'sqlite:///{db_path}')}); "
                        f"command.upgrade(cfg, 'head')",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    env={
                        **os.environ,
                        "PYTHONPATH": str(project_dir_abs),
                        "TERM": "dumb",
                        "PYTHONIOENCODING": "utf-8",
                    },
                )

                if upgrade_result.returncode != 0:
                    logger.error(f"Alembic upgrade failed: {upgrade_result.stderr}")
                    fh.flush()
                    result["migration_status"] = "failed"
                    result["error"] = f"Upgrade failed: {upgrade_result.stderr}"
                    return result
                logger.info("Alembic upgrade head completed.")
                fh.flush()
            except subprocess.TimeoutExpired:
                logger.error("Alembic upgrade timed out after 60 seconds")
                fh.flush()
                result["migration_status"] = "failed"
                result["error"] = "Upgrade timed out after 60 seconds"
                return result
            except Exception as e:
                logger.error(f"Alembic upgrade subprocess failed: {e}", exc_info=True)
                fh.flush()
                result["migration_status"] = "failed"
                result["error"] = f"Upgrade subprocess failed: {e}"
                return result

            logger.info("Running Alembic autogenerate...")
            fh.flush()
            try:  # Run autogenerate in subprocess to avoid terminal interaction issues
                revision_result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        f"from alembic.config import Config; from alembic import command; "
                        f"cfg = Config({repr(str(alembic_ini))}); cfg.set_main_option('script_location', {repr(str(alembic_dir))}); "
                        f"cfg.set_main_option('sqlalchemy.url', {repr(f'sqlite:///{db_path}')}); "
                        f"command.revision(cfg, message='{migration_msg}', autogenerate=True, rev_id='{migration_id}')",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    env={
                        **os.environ,
                        "PYTHONPATH": str(project_dir_abs),
                        "TERM": "dumb",
                        "PYTHONIOENCODING": "utf-8",
                    },
                )

                if revision_result.returncode != 0:
                    logger.error(
                        f"Alembic autogenerate failed: {revision_result.stderr}"
                    )
                    fh.flush()
                    result["migration_status"] = "failed"
                    result["error"] = f"Autogenerate failed: {revision_result.stderr}"
                    return result
                logger.info("Alembic autogenerate completed.")
                fh.flush()
                result["migration_status"] = "success"
            except subprocess.TimeoutExpired:
                logger.error("Alembic autogenerate timed out after 120 seconds")
                fh.flush()
                result["migration_status"] = "failed"
                result["error"] = "Autogenerate timed out after 120 seconds"
                return result
            except Exception as e:
                logger.error(
                    f"Alembic autogenerate subprocess failed: {e}", exc_info=True
                )
                fh.flush()
                result["migration_status"] = "failed"
                result["error"] = f"Autogenerate subprocess failed: {e}"
                return result  # Find the latest migration file
            migration_files = sorted(
                versions_dir.glob("*.py"), key=os.path.getmtime, reverse=True
            )
            if migration_files:
                migration_file = migration_files[0]
                with open(migration_file, "r") as f:
                    migration_content = f.read()
                # Ensure project_dir is absolute for relative_to calculation
                project_dir_abs = (
                    project_dir.resolve()
                    if hasattr(project_dir, "resolve")
                    else Path(project_dir).resolve()
                )
                migration_file_info = {
                    "file_path": migration_file.relative_to(project_dir_abs).as_posix(),
                    "generated_code": migration_content,
                    "content_base64": LangchainService.encode_content(
                        migration_content
                    ),
                    "file_hash": LangchainService.generate_file_hash(migration_content),
                }
                result["migration_files"].append(migration_file_info)
                result["migration_component"] = {
                    "file_path": migration_file.relative_to(project_dir_abs).as_posix(),
                    "generated_code": migration_content,
                    "content_base64": LangchainService.encode_content(
                        migration_content
                    ),
                    "file_hash": LangchainService.generate_file_hash(migration_content),
                    "entity_name": entity_name,
                }
                result["migration_status"] = "success"
            else:
                logger.warning("No migration files found after autogenerate")
                fh.flush()
                result["migration_status"] = "failed"
                result["error"] = "No migration files found after autogenerate"
        except Exception as e:
            logger.error(f"Migration generation failed: {e}", exc_info=True)
            fh.flush()
            result["migration_status"] = "failed"
            result["error"] = str(e)
        finally:
            fh.close()  # Ensure function always returns here so the rest of the flow continues
        return result

    async def _read_related_endpoints(
        self, project_id: str, entity_name: str, **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Read related endpoint files for the same endpoint path but different HTTP methods.

        Args:
            project_id (str): The project identifier
            entity_name (str): The entity name
            **kwargs: Additional parameters including endpoint_path and method

        Returns:
            List[Dict[str, Any]]: List of related endpoint information
        """
        related_endpoints = []

        try:
            endpoint_path = kwargs.get("endpoint_path", "")
            current_method = kwargs.get("method", "").lower()

            if not endpoint_path:
                logger.debug(
                    "No endpoint_path provided, skipping related endpoints reading"
                )
                return related_endpoints

            # Extract the last segment of the path for filename matching
            path_segments = endpoint_path.strip("/").split("/")
            last_segment = path_segments[-1] if path_segments else endpoint_path

            # Define common HTTP methods to check for
            http_methods = ["get", "post", "put", "delete", "patch", "head", "options"]

            # Build the project directory path
            from pathlib import Path

            project_dir = Path("repos") / project_id
            endpoints_dir = project_dir / "endpoints"

            if not endpoints_dir.exists():
                logger.debug(f"Endpoints directory {endpoints_dir} does not exist")
                return related_endpoints

            # Check for related endpoint files
            for method in http_methods:
                if method == current_method:
                    continue  # Skip the current method we're generating

                endpoint_file = endpoints_dir / f"{last_segment}.{method}.py"

                if endpoint_file.exists():
                    try:
                        with open(endpoint_file, "r", encoding="utf-8") as f:
                            file_content = f.read()

                        # Extract key information from the endpoint file
                        endpoint_info = {
                            "method": method.upper(),
                            "file_path": str(endpoint_file.relative_to(project_dir)),
                            "content": file_content,
                            "entity_name": self.extract_entity_from_code(file_content)
                            or entity_name,
                            "has_database_operations": self.needs_database(
                                file_content
                            ),
                            "has_schema_usage": self.needs_schema(file_content),
                            "has_helper_usage": self.needs_helpers(file_content),
                        }  # Extract route patterns and function names for additional context
                        route_pattern = re.search(
                            r'@router\.\w+\([\'"]([^\'"]+)[\'"]', file_content
                        )
                        if route_pattern:
                            endpoint_info["route_pattern"] = route_pattern.group(1)

                        function_pattern = re.search(r"def\s+(\w+)\s*\(", file_content)
                        if function_pattern:
                            endpoint_info["function_name"] = function_pattern.group(1)

                        related_endpoints.append(endpoint_info)
                        logger.info(
                            f"Found related endpoint: {method.upper()} {endpoint_path} -> {endpoint_file}"
                        )

                    except Exception as e:
                        logger.warning(
                            f"Error reading related endpoint file {endpoint_file}: {str(e)}"
                        )

            logger.info(
                f"Found {len(related_endpoints)} related endpoint files for {endpoint_path}"
            )

        except Exception as e:
            logger.error(f"Error in _read_related_endpoints: {str(e)}")

        return related_endpoints

    async def discover_similar_endpoint_patterns(
        self,
        project_id: str,
        endpoint_path: str,
        method: str,
        entity_name: str,
        **kwargs,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Discover and read similar endpoint patterns to provide enhanced context for code generation.

        This method finds:
        1. Related endpoints (same path, different methods)
        2. Similar path endpoints (similar URL patterns)
        3. Same method endpoints (same HTTP method, different entities)
        4. Entity-related endpoints (endpoints working with related entities)

        Args:
            project_id (str): The project identifier
            endpoint_path (str): The current endpoint path
            method (str): The current HTTP method
            entity_name (str): The current entity name
            **kwargs: Additional parameters        Returns:
            Dict[str, List[Dict[str, Any]]]: Categorized similar endpoints context
        """
        context = {
            "related_endpoints": [],  # Same path, different methods
            "similar_paths": [],  # Similar URL patterns
            "same_method_endpoints": [],  # Same method, different entities
            "entity_related": [],  # Related entity endpoints
        }

        try:
            project_dir = Path("repos") / project_id
            endpoints_dir = project_dir / "endpoints"

            if not endpoints_dir.exists():
                logger.debug(f"Endpoints directory {endpoints_dir} does not exist")
                return context

            # Get related endpoints (same path, different methods)
            context["related_endpoints"] = await self._read_related_endpoints(
                project_id, entity_name, endpoint_path=endpoint_path, method=method
            )

            # Discover all endpoint files for pattern analysis
            all_endpoint_files = self._discover_all_endpoint_files(endpoints_dir)

            # Extract current endpoint components for similarity matching
            current_path_segments = endpoint_path.strip("/").split("/")
            current_entity = entity_name.lower() if entity_name else ""
            current_method_lower = method.lower()

            for endpoint_file_info in all_endpoint_files:
                try:
                    file_path = endpoint_file_info["file_path"]
                    file_method = endpoint_file_info["method"]
                    file_entity = endpoint_file_info["entity"]
                    file_content = endpoint_file_info["content"]
                    file_url_path = endpoint_file_info["url_path"]

                    # Skip if it's the current endpoint or already in related endpoints
                    if (
                        file_url_path == endpoint_path
                        and file_method.lower() == current_method_lower
                    ):
                        continue

                    # Check for similar paths (shared path segments or patterns)
                    if self._has_similar_path_pattern(
                        current_path_segments, file_url_path
                    ):
                        context["similar_paths"].append(
                            {
                                "method": file_method.upper(),
                                "path": file_url_path,
                                "file_path": file_path,
                                "entity_name": file_entity,
                                "content_preview": self._extract_content_preview(
                                    file_content
                                ),
                                "route_pattern": self._extract_route_pattern(
                                    file_content
                                ),
                                "function_name": self._extract_function_name(
                                    file_content
                                ),
                                "has_database_operations": self.needs_database(
                                    file_content
                                ),
                                "similarity_score": self._calculate_path_similarity(
                                    current_path_segments, file_url_path
                                ),
                            }
                        )

                    # Check for same method endpoints (different entities)
                    if (
                        file_method.lower() == current_method_lower
                        and file_entity != current_entity
                        and file_entity
                    ):
                        context["same_method_endpoints"].append(
                            {
                                "method": file_method.upper(),
                                "path": file_url_path,
                                "file_path": file_path,
                                "entity_name": file_entity,
                                "content_preview": self._extract_content_preview(
                                    file_content
                                ),
                                "route_pattern": self._extract_route_pattern(
                                    file_content
                                ),
                                "function_name": self._extract_function_name(
                                    file_content
                                ),
                                "has_database_operations": self.needs_database(
                                    file_content
                                ),
                            }
                        )

                    # Check for entity-related endpoints
                    if file_entity != current_entity and self._entities_are_related(
                        current_entity, file_entity
                    ):
                        context["entity_related"].append(
                            {
                                "method": file_method.upper(),
                                "path": file_url_path,
                                "file_path": file_path,
                                "entity_name": file_entity,
                                "content_preview": self._extract_content_preview(
                                    file_content
                                ),
                                "route_pattern": self._extract_route_pattern(
                                    file_content
                                ),
                                "function_name": self._extract_function_name(
                                    file_content
                                ),
                                "has_database_operations": self.needs_database(
                                    file_content
                                ),
                                "relationship_type": self._determine_entity_relationship(
                                    current_entity, file_entity
                                ),
                            }
                        )

                except Exception as e:
                    logger.warning(
                        f"Error processing endpoint file {endpoint_file_info.get('file_path', 'unknown')}: {str(e)}"
                    )

            # Sort and limit results for performance
            context["similar_paths"] = sorted(
                context["similar_paths"],
                key=lambda x: x.get("similarity_score", 0),
                reverse=True,
            )[:5]
            context["same_method_endpoints"] = context["same_method_endpoints"][:5]
            context["entity_related"] = context["entity_related"][:5]

            total_found = sum(len(context[key]) for key in context)
            logger.info(
                f"Discovered {total_found} similar endpoint patterns for context enhancement"
            )

        except Exception as e:
            logger.error(f"Error in discover_similar_endpoint_patterns: {str(e)}")

        return context

    def _discover_all_endpoint_files(self, endpoints_dir: Path) -> List[Dict[str, Any]]:
        """
        Discover all endpoint files in the endpoints directory structure.

        Args:
            endpoints_dir (Path): Path to the endpoints directory

        Returns:
            List[Dict[str, Any]]: List of endpoint file information
        """
        endpoint_files = []

        try:
            for file_path in endpoints_dir.rglob("*.py"):
                if file_path.name.startswith("__"):
                    continue  # Skip __init__.py and other special files

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Extract method from filename (e.g., "users.get.py" -> "get")
                    method = self._extract_method_from_filename(file_path.name)

                    # Extract entity from filename or content
                    entity = self._extract_entity_from_filename(
                        file_path.name
                    ) or self.extract_entity_from_code(content)

                    # Extract URL path from file structure and content
                    url_path = self._extract_url_path_from_file(
                        file_path, endpoints_dir, content
                    )

                    endpoint_files.append(
                        {
                            "file_path": str(
                                file_path.relative_to(endpoints_dir.parent)
                            ),
                            "method": method or "UNKNOWN",
                            "entity": entity or "",
                            "url_path": url_path,
                            "content": content,
                        }
                    )

                except Exception as e:
                    logger.warning(f"Error reading endpoint file {file_path}: {str(e)}")

        except Exception as e:
            logger.error(f"Error discovering endpoint files: {str(e)}")

        return endpoint_files

    def _extract_method_from_filename(self, filename: str) -> Optional[str]:
        """Extract HTTP method from filename (e.g., 'users.get.py' -> 'get')."""
        parts = filename.replace(".py", "").split(".")
        http_methods = ["get", "post", "put", "delete", "patch", "head", "options"]

        for part in reversed(parts):
            if part.lower() in http_methods:
                return part.lower()
        return None

    def _extract_entity_from_filename(self, filename: str) -> Optional[str]:
        """Extract entity name from filename (e.g., 'users.get.py' -> 'users')."""
        base_name = filename.replace(".py", "")
        parts = base_name.split(".")

        # Return the first part as the potential entity name
        if parts and parts[0]:
            return self._to_singular_entity_name(parts[0])
        return None

    def _extract_url_path_from_file(
        self, file_path: Path, endpoints_dir: Path, content: str
    ) -> str:
        """Extract URL path from file structure and content."""  # First try to extract from route decorator in content
        route_match = re.search(r'@router\.\w+\([\'"]([^\'"]+)[\'"]', content)
        if route_match:
            return route_match.group(1)

        # Fallback to file structure
        relative_path = file_path.relative_to(endpoints_dir)
        path_parts = list(relative_path.parts[:-1])  # Exclude filename

        # Extract base name without method
        filename_base = file_path.stem
        if "." in filename_base:
            filename_base = filename_base.split(".")[0]

        path_parts.append(filename_base)
        return "/" + "/".join(path_parts) if path_parts else f"/{filename_base}"

    def _has_similar_path_pattern(
        self, current_segments: List[str], other_path: str
    ) -> bool:
        """Check if two paths have similar patterns."""
        other_segments = other_path.strip("/").split("/")

        # Skip empty paths
        if not current_segments or not other_segments:
            return False

        # Check for shared segments
        current_set = set(current_segments)
        other_set = set(other_segments)
        shared_segments = current_set.intersection(other_set)

        # Consider similar if they share at least one meaningful segment
        meaningful_shared = len(shared_segments) > 0 and any(
            len(seg) > 2 for seg in shared_segments
        )

        # Also check for similar structure (same depth, similar patterns)
        similar_structure = (
            abs(len(current_segments) - len(other_segments)) <= 1
            and len(current_segments) > 1
            and len(other_segments) > 1
        )

        return meaningful_shared or similar_structure

    def _calculate_path_similarity(
        self, current_segments: List[str], other_path: str
    ) -> float:
        """Calculate similarity score between two paths."""
        other_segments = other_path.strip("/").split("/")

        if not current_segments or not other_segments:
            return 0.0

        # Calculate Jaccard similarity
        current_set = set(current_segments)
        other_set = set(other_segments)

        intersection = len(current_set.intersection(other_set))
        union = len(current_set.union(other_set))

        if union == 0:
            return 0.0

        jaccard_score = intersection / union

        # Bonus for similar structure
        structure_bonus = (
            0.1 if abs(len(current_segments) - len(other_segments)) <= 1 else 0
        )

        return min(1.0, jaccard_score + structure_bonus)

    def _entities_are_related(self, entity1: str, entity2: str) -> bool:
        """Check if two entities are related (e.g., User and UserProfile)."""
        if not entity1 or not entity2:
            return False

        entity1_lower = entity1.lower()
        entity2_lower = entity2.lower()

        # Check for substring relationships
        if entity1_lower in entity2_lower or entity2_lower in entity1_lower:
            return True

        # Check for common patterns
        common_patterns = [
            (r"user", r"profile|setting|preference|account"),
            (r"product", r"category|order|cart|inventory"),
            (r"order", r"item|payment|shipping|invoice"),
            (r"post", r"comment|tag|category"),
            (r"project", r"task|member|team"),
        ]

        for pattern1, pattern2 in common_patterns:
            if (
                re.search(pattern1, entity1_lower)
                and re.search(pattern2, entity2_lower)
            ) or (
                re.search(pattern2, entity1_lower)
                and re.search(pattern1, entity2_lower)
            ):
                return True

        return False

    def _determine_entity_relationship(self, entity1: str, entity2: str) -> str:
        """Determine the type of relationship between two entities."""
        if not entity1 or not entity2:
            return "unknown"

        entity1_lower = entity1.lower()
        entity2_lower = entity2.lower()

        # Parent-child relationships
        if entity1_lower in entity2_lower:
            return "parent-child"
        if entity2_lower in entity1_lower:
            return "child-parent"

        # Domain-specific relationships
        if "user" in entity1_lower and any(
            term in entity2_lower for term in ["profile", "setting", "preference"]
        ):
            return "composition"
        if "product" in entity1_lower and any(
            term in entity2_lower for term in ["category", "tag"]
        ):
            return "classification"
        if "order" in entity1_lower and "item" in entity2_lower:
            return "aggregation"

        return "related"

    def _extract_content_preview(self, content: str) -> str:
        """Extract a preview of the endpoint content (docstring or first few lines)."""
        lines = content.split("\n")

        # Look for docstring
        in_docstring = False
        docstring_lines = []

        for line in lines:
            stripped = line.strip()
            if '"""' in stripped or "'''" in stripped:
                if not in_docstring:
                    in_docstring = True
                    # Include the line with the opening quotes
                    docstring_lines.append(stripped)
                else:
                    # Closing quotes
                    docstring_lines.append(stripped)
                    break
            elif in_docstring:
                docstring_lines.append(stripped)

        if docstring_lines:
            preview = " ".join(docstring_lines)
            return preview[:200] + "..." if len(preview) > 200 else preview

        # Fallback to first meaningful lines
        meaningful_lines = [
            line.strip()
            for line in lines[:10]
            if line.strip() and not line.strip().startswith("#")
        ]
        preview = " ".join(meaningful_lines)
        return preview[:200] + "..." if len(preview) > 200 else preview

    def _extract_route_pattern(self, content: str) -> Optional[str]:
        """Extract route pattern from endpoint content."""
        match = re.search(r'@router\.\w+\([\'"]([^\'"]+)[\'"]', content)
        return match.group(1) if match else None

    def _extract_function_name(self, content: str) -> Optional[str]:
        """Extract function name from endpoint content."""
        match = re.search(r"def\s+(\w+)\s*\(", content)
        return match.group(1) if match else None

    def _to_singular_entity_name(self, name: str) -> str:
        """Convert plural entity name to singular (basic implementation)."""
        if name.endswith("ies"):
            return name[:-3] + "y"
        elif name.endswith("s") and len(name) > 1:
            return name[:-1]
        return name
