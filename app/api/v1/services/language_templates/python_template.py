import asyncio
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.api.v1.services.git_service import GitService
from app.api.v1.services.langchain_service import LangchainService
from app.api.v1.services.language_templates.language_template import LanguageTemplate

logger = logging.getLogger(__name__)


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
            api_docs_file = f"docs/{last_segment}.md"
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
        result["file_path"] = self.get_component_paths(
            project_id, entity_name, **kwargs
        )[component_type]
        result["entity_name"] = entity_name

        if "method" in kwargs:
            result["method"] = kwargs["method"]
        if "endpoint_path" in kwargs:
            result["endpoint_path"] = kwargs["endpoint_path"]

        return result

    async def generate_dockerfile(self, project_id: str, entity_name: str) -> str:
        """
        Generate a Dockerfile for Python FastAPI application.

        Args:
            project_id (str): The project ID
            entity_name (str): The name of the entity

        Returns:
            str: Dockerfile content
        """
        try:
            # Use the prompt template via LangchainService
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
            import sqlite3

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
                try:
                    # Get the project_id from the project_dir path
                    project_id = project_dir.name

                    # Read the database as binary data
                    with open(sqlite_path, "rb") as f:
                        sqlite_data = f.read()

                    relative_path = str(sqlite_path.relative_to(project_dir))
                    commit_message = f"Update SQLite database with new tables: {', '.join(tables_created)}"

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

    async def generate_migration(self, project_dir: Path, entity_name: str) -> dict:
        """
        Generates migration files for an entity without applying them.
        This is separated from run_migrations to allow users to explicitly trigger migrations later.

        Returns:
            dict: Dictionary containing migration files and component information
        """
        logger.info(f"Generating migration for {entity_name} in {project_dir}")
        result = {"migration_files": [], "migration_component": None}

        # Set up directories
        versions_dir = project_dir / "alembic" / "versions"
        versions_dir.mkdir(exist_ok=True, parents=True)

        # Find latest migration ID
        latest_migration_id = self._find_latest_migration_id(project_dir, versions_dir)

        # Get model code for template context
        snake_case_entity = self._to_snake_case(entity_name)
        model_file = project_dir / "models" / f"{snake_case_entity}.py"
        model_code = ""

        if model_file.exists():
            try:
                model_code = model_file.read_text()
                logger.info(f"Found model file: {model_file}")
            except Exception as e:
                logger.warning(f"Could not read model file: {str(e)}")

        # Generate migration using template
        logger.info(
            f"Generating migration with template using parent ID: {latest_migration_id}"
        )
        try:
            from app.api.v1.services.langchain_service import LangchainService

            migration_result = await LangchainService.generate_code_with_template(
                template_name="migration",
                language="python",
                entity_name=entity_name,
                latest_migration_id=latest_migration_id,
                model_code=model_code,
            )

            migration_content = migration_result.get("generated_code", "")
            if not migration_content:
                raise ValueError("Failed to generate migration content from template")

            # Log the first few lines for debugging
            first_lines = "\n".join(migration_content.split("\n")[:10])
            logger.info(f"Generated migration content (first 10 lines):\n{first_lines}")

            # Fix PostgreSQL-specific types for SQLite
            migration_content = migration_content.replace(
                "from sqlalchemy.dialects.postgresql import UUID",
                "# Using String type instead of UUID for SQLite compatibility",
            )
            migration_content = migration_content.replace(
                "UUID(as_uuid=True)", "sa.String()"
            )

            # Fix empty down_revision or incorrect down_revision
            if (
                "down_revision = ''" in migration_content
                or 'down_revision = ""' in migration_content
            ):
                migration_content = re.sub(
                    r"down_revision\s*=\s*['\"]?['\"]",
                    f"down_revision = '{latest_migration_id}'",
                    migration_content,
                )
                logger.info(f"Fixed empty down_revision to use {latest_migration_id}")

            # Make sure the migration references the correct parent
            down_rev_pattern = r"down_revision\s*=\s*['\"]([^'\"]+)['\"]"
            current_down_rev = re.search(down_rev_pattern, migration_content)
            if current_down_rev and current_down_rev.group(1) != latest_migration_id:
                migration_content = re.sub(
                    down_rev_pattern,
                    f"down_revision = '{latest_migration_id}'",
                    migration_content,
                )
                logger.info(
                    f"Updated down_revision to use correct parent: {latest_migration_id}"
                )

            # Check for existing migration for this entity
            existing_migration = False
            for existing_file in versions_dir.glob("*.py"):
                try:
                    content = existing_file.read_text()
                    if (
                        f"op.create_table('{snake_case_entity}s'" in content
                        or f'op.create_table("{snake_case_entity}s"' in content
                    ):
                        existing_migration = True
                        logger.info(
                            f"Found existing migration for {entity_name} at {existing_file}"
                        )
                        break
                except Exception:
                    pass

            if not existing_migration:
                # Write the migration file
                migration_file = versions_dir / f"create_{snake_case_entity}_table.py"
                logger.info(f"Creating migration file: {migration_file}")
                with open(migration_file, "w") as f:
                    f.write(migration_content)

                # Add to result
                from app.api.v1.services.langchain_service import LangchainService

                migration_file_info = {
                    "file_path": str(migration_file.relative_to(project_dir)),
                    "generated_code": migration_content,
                    "content_base64": LangchainService.encode_content(
                        migration_content
                    ),
                    "file_hash": LangchainService.generate_file_hash(migration_content),
                }
                result["migration_files"].append(migration_file_info)

                # Create migration component info
                result["migration_component"] = {
                    "file_path": str(migration_file.relative_to(project_dir)),
                    "generated_code": migration_content,
                    "content_base64": LangchainService.encode_content(
                        migration_content
                    ),
                    "file_hash": LangchainService.generate_file_hash(migration_content),
                    "entity_name": entity_name,
                }
            else:
                logger.info(
                    f"Skipping migration creation as it already exists for {entity_name}"
                )

        except Exception as e:
            logger.error(f"Error generating migration: {str(e)}")

        return result

    def _find_latest_migration_id(self, project_dir: Path, versions_dir: Path) -> str:
        """
        Determines the latest Alembic migration ID for a given project.
        This method attempts to find the most recent migration revision by:
          1. Parsing all migration files in the specified versions directory to identify head revisions.
          2. If no head revision is found in the files, querying the project's SQLite database for the current Alembic version.
          3. If neither approach yields a result, returning a default migration ID.
        Args:
            project_dir (Path): The root directory of the project, used to locate the SQLite database.
            versions_dir (Path): The directory containing Alembic migration files.
        Returns:
            str: The latest migration ID, either determined from migration files, the database, or a default value.
        """
        latest_migration_id = None
        try:
            # Find the latest migration ID from existing files
            migration_files = list(versions_dir.glob("*.py"))

            if migration_files:
                logger.info(f"Listing migrations directly from {versions_dir}")
                logger.info(f"Found {len(migration_files)} migration files:")

                revision_ids = {}
                for migration_file in migration_files:
                    try:
                        content = migration_file.read_text()
                        rev_match = re.search(
                            r"revision\s*=\s*['\"]([^'\"]+)['\"]", content
                        )
                        if rev_match:
                            rev_id = rev_match.group(1)
                            down_rev_match = re.search(
                                r"down_revision\s*=\s*([^,\n]+)", content
                            )
                            down_rev = None
                            if down_rev_match:
                                down_rev_str = down_rev_match.group(1).strip()
                                if down_rev_str not in ("None", "none", "''", '""'):
                                    down_rev = down_rev_str.strip("'\"")
                            revision_ids[rev_id] = down_rev
                            logger.info(
                                f"  - {migration_file.name}: revision={rev_id}, down_revision={down_rev}"
                            )
                    except Exception as e:
                        logger.warning(
                            f"Error reading migration {migration_file}: {str(e)}"
                        )

                # Find head revisions
                if revision_ids:
                    all_revs = set(revision_ids.keys())
                    child_revs = set(r for r in revision_ids.values() if r is not None)
                    head_revs = all_revs - child_revs

                    if head_revs:
                        latest_migration_id = list(head_revs)[
                            0
                        ]  # Just take the first one if multiple heads
                        logger.info(
                            f"Found head revisions through direct parsing: {head_revs}"
                        )
                        logger.info(
                            f"Using latest migration ID from direct parsing: {latest_migration_id}"
                        )

            if not latest_migration_id:
                # Try to get it from the database if it exists
                sqlite_path = project_dir / "storage" / "db" / "db.sqlite"
                if sqlite_path.exists():
                    try:
                        import sqlite3

                        conn = sqlite3.connect(str(sqlite_path))
                        cursor = conn.cursor()

                        # Check if alembic_version table exists
                        cursor.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version';"
                        )
                        has_alembic_table = cursor.fetchone() is not None

                        if has_alembic_table:
                            cursor.execute("SELECT version_num FROM alembic_version;")
                            version_row = cursor.fetchone()
                            if version_row:
                                latest_migration_id = version_row[0]
                                logger.info(
                                    f"Using current database version as latest: {latest_migration_id}"
                                )

                        conn.close()
                    except Exception as e:
                        logger.warning(f"Error checking database version: {str(e)}")

            if not latest_migration_id:
                # If still no head found, use a default
                latest_migration_id = "e77b933ce306"  # Use a default ID
                logger.info(
                    f"No head revisions found, using default ID: {latest_migration_id}"
                )
        except Exception as e:
            logger.warning(f"Error finding latest migration ID: {str(e)}")
            latest_migration_id = "e77b933ce306"  # Use a default ID

        return latest_migration_id

    async def run_migrations_with_logs(self, project_dir: Path, logger) -> dict:
        """
        Runs simplified database migrations while streaming logs to the provided logger.

        Args:
            project_dir (Path): The root directory of the project
            logger: An async logger object to stream logs to

        Returns:
            dict: Migration results
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
            import sqlite3

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
                    )

                    # Read the database as binary data
                    with open(sqlite_path, "rb") as f:
                        sqlite_data = f.read()
                    await logger.info(
                        f"Read {len(sqlite_data)} bytes from database file"
                    )

                    relative_path = str(sqlite_path.relative_to(project_dir))
                    commit_message = f"Update SQLite database with new tables: {', '.join(tables_created)}"

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
