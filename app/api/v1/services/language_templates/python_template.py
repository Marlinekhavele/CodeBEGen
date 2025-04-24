import logging
import re
from typing import Any, Dict, List, Optional
import subprocess
from pathlib import Path
import datetime
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
        else:
            # Fallback to entity-based naming if endpoint path is not provided
            endpoint_file = f"endpoints/{snake_case_entity}_endpoint.py"

        return {
            "endpoint": endpoint_file,
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
            "components": ["model", "schema", "migration", "helpers", "endpoint", "dockerfile", "api_docs", "database"],
            "commit_order": ["model", "schema", "migration", "helpers", "endpoint",  "dockerfile", "api_docs", "database"],
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

    async def run_migrations(self, project_dir: Path, entity_name: str):
        """
        Runs Alembic database migrations for a given project directory and entity.
        Handles SQLite compatibility issues.
        """
        alembic_ini = project_dir / "alembic.ini"
        logger.info(f"Running migrations for {entity_name} in {project_dir}")
        logger.info(f"Checking for alembic.ini at {alembic_ini}")
        
        # Check if alembic is set up
        alembic_initialized = alembic_ini.exists()
        
        if not alembic_initialized:
            logger.warning(f"alembic.ini not found in {project_dir}. Using template-based migration generation.")
            # Fall back to template-based migration
            return await self._generate_template_migration(project_dir, entity_name)
        
        logger.info(f"Found alembic.ini in {project_dir}. Running Alembic migrations.")
        
        # Create storage directory for SQLite database
        storage_dir = project_dir / "storage" / "db"
        storage_dir.mkdir(exist_ok=True, parents=True)
        sqlite_path = storage_dir / "db.sqlite"
        
        # Update database connection string in alembic.ini
        try:
            ini_content = alembic_ini.read_text()
            relative_path = str(sqlite_path.relative_to(project_dir)).replace("\\", "/")
            
            if "sqlalchemy.url = " in ini_content and "sqlite:///" not in ini_content:
                new_content = re.sub(
                    r"sqlalchemy\.url\s*=\s*.*", 
                    f"sqlalchemy.url = sqlite:///{relative_path}",
                    ini_content
                )
                alembic_ini.write_text(new_content)
                logger.info(f"Updated database connection string in alembic.ini")
            else:
                logger.info(f"Using database path: sqlite:///{relative_path}")
                logger.info("Database connection string already set or not found")
        except Exception as e:
            logger.warning(f"Could not update alembic.ini: {str(e)}")
        
        # Get existing migrations
        versions_dir = project_dir / "alembic" / "versions"
        versions_dir.mkdir(exist_ok=True, parents=True)
        
        try:
            existing_migrations = list(versions_dir.glob("*.py"))
            logger.info(f"Checking existing migrations in {versions_dir}")
            logger.info(f"Found {len(existing_migrations)} existing migration files:")
            
            for migration_file in existing_migrations:
                try:
                    content = migration_file.read_text()
                    rev_match = re.search(r"revision\s*=\s*['\"]([^'\"]+)['\"]", content)
                    rev_id = rev_match.group(1) if rev_match else "unknown"
                    logger.info(f"  - {migration_file.name}: revision={rev_id}")
                except Exception as e:
                    logger.warning(f"  - {migration_file.name}: Error reading {str(e)}")
        except Exception as e:
            logger.warning(f"Error listing migrations: {str(e)}")
        
        # Skip Alembic autogenerate completely since it doesn't handle SQLite well
        # Instead, always use our template-based approach which will be SQLite-compatible
        logger.info(f"Using template-based migration for SQLite compatibility")
        return await self._generate_template_migration(project_dir, entity_name)
        
    async def _generate_template_migration(self, project_dir: Path, entity_name: str):
        """
        Generate migration using template approach for SQLite compatibility.
        """
        logger.info(f"Using template-based migration generation for {entity_name}")
        
        # Create storage directory for SQLite database
        storage_dir = project_dir / "storage" / "db"
        storage_dir.mkdir(exist_ok=True, parents=True)
        sqlite_path = storage_dir / "db.sqlite"
        
        # Create the versions directory if it doesn't exist
        versions_dir = project_dir / "alembic" / "versions"
        versions_dir.mkdir(exist_ok=True, parents=True)
        
        # Find migrations directly in the project directory
        latest_migration_id = None
        try:
            # Explicitly list migrations in this project's versions directory
            logger.info(f"Listing migrations directly from {versions_dir}")
            migration_files = list(versions_dir.glob("*.py"))
            
            if migration_files:
                # Extract revision info from each file
                logger.info(f"Found {len(migration_files)} migration files:")
                revision_ids = {}
                
                for migration_file in migration_files:
                    try:
                        content = migration_file.read_text()
                        rev_match = re.search(r"revision\s*=\s*['\"]([^'\"]+)['\"]", content)
                        if rev_match:
                            rev_id = rev_match.group(1)
                            
                            # Get down_revision if available
                            down_rev_match = re.search(r"down_revision\s*=\s*([^,\n]+)", content)
                            down_rev = None
                            if down_rev_match:
                                down_rev_str = down_rev_match.group(1).strip()
                                if down_rev_str not in ("None", "none", "''", '""'):
                                    down_rev = down_rev_str.strip("'\"")
                            
                            revision_ids[rev_id] = down_rev
                            logger.info(f"  - {migration_file.name}: revision={rev_id}, down_revision={down_rev}")
                    except Exception as e:
                        logger.warning(f"  - {migration_file.name}: Error reading {str(e)}")
                
                # Find the head revisions (no other revision points to them)
                if revision_ids:
                    # All revisions
                    all_revs = set(revision_ids.keys())
                    # Revisions that are referenced as down_revisions
                    child_revs = set(r for r in revision_ids.values() if r is not None)
                    # Head revisions are those that are not down_revisions of any other revision
                    head_revs = all_revs - child_revs
                    
                    if head_revs:
                        logger.info(f"Found head revisions through direct parsing: {head_revs}")
                        latest_migration_id = max(head_revs)
                        logger.info(f"Using latest migration ID from direct parsing: {latest_migration_id}")
        except Exception as e:
            logger.warning(f"Error analyzing migrations: {str(e)}")

        # Use default ID if none found
        if not latest_migration_id:
            # Check for initial migration
            for migration_file in versions_dir.glob("*initial*.py"):
                try:
                    content = migration_file.read_text()
                    rev_match = re.search(r"revision\s*=\s*['\"]([^'\"]+)['\"]", content)
                    if rev_match:
                        latest_migration_id = rev_match.group(1)
                        logger.info(f"Using initial migration ID: {latest_migration_id}")
                        break
                except Exception:
                    pass
                    
            # Default fallback
            if not latest_migration_id:
                latest_migration_id = "8b7c9d0e1f2a"  # Default ID
                logger.info(f"Using default template migration ID: {latest_migration_id}")
        
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
        
        # Generate migration using the template manager
        try:
            from app.api.v1.services.langchain_service import LangchainService
            
            logger.info(f"Generating migration with template using parent ID: {latest_migration_id}")
            migration_result = await LangchainService.generate_code_with_template(
                template_name="migration",
                language="python",
                entity_name=entity_name,
                latest_migration_id=latest_migration_id,
                model_code=model_code
            )
            
            migration_content = migration_result.get("generated_code", "")
            
            if not migration_content:
                raise ValueError("Failed to generate migration content from template")
            
            # Fix PostgreSQL-specific types for SQLite
            migration_content = migration_content.replace(
                "from sqlalchemy.dialects.postgresql import UUID", 
                "# Using String type instead of UUID for SQLite compatibility"
            )
            migration_content = migration_content.replace(
                "UUID(as_uuid=True)", 
                "sa.String()"
            )
            
            # Fix empty string down_revision
            if "down_revision = ''" in migration_content or 'down_revision = ""' in migration_content:
                migration_content = re.sub(
                    r"down_revision\s*=\s*['\"]?['\"]",
                    f"down_revision = '{latest_migration_id}'",
                    migration_content
                )
                logger.info(f"Fixed empty down_revision to use latest migration ID: {latest_migration_id}")
            
            # Log a sample of the migration content
            content_preview = migration_content.split("\n")[:10]
            logger.info(f"Generated migration content (first 10 lines):\n{chr(10).join(content_preview)}")
            
            # Check if we already have a migration for this entity
            existing_order_migration = False
            for existing_file in versions_dir.glob("*.py"):
                try:
                    content = existing_file.read_text()
                    if f"op.create_table('{snake_case_entity}s'" in content or f'op.create_table("{snake_case_entity}s"' in content:
                        existing_order_migration = True
                        logger.info(f"Found existing migration for {entity_name} at {existing_file}")
                        break
                except Exception:
                    pass
            
            if not existing_order_migration:
                # Write the migration file
                migration_file = versions_dir / f"create_{snake_case_entity}_table.py"
                logger.info(f"Creating migration file: {migration_file}")
                with open(migration_file, 'w') as f:
                    f.write(migration_content)
                
                # Try to apply the migration if alembic.ini exists
                if (project_dir / "alembic.ini").exists():
                    try:
                        logger.info("Applying template-generated migration")
                        result = subprocess.run(
                            ["alembic", "upgrade", "head"], 
                            cwd=project_dir, 
                            check=False,
                            capture_output=True,
                            text=True
                        )
                        if result.returncode == 0:
                            logger.info(f"Successfully applied template migration: {result.stdout}")
                        else:
                            logger.warning(f"Could not apply template migration: {result.stderr}")
                    except Exception as apply_error:
                        logger.warning(f"Could not apply template-generated migration: {str(apply_error)}")
            
        except Exception as e:
            logger.error(f"Error generating template-based migration: {str(e)}")
        
        # Create an empty SQLite database if it doesn't exist
        if not sqlite_path.exists():
            try:
                import sqlite3
                conn = sqlite3.connect(str(sqlite_path))
                conn.close()
                logger.info(f"Created empty SQLite database at {sqlite_path}")
            except Exception as db_error:
                logger.error(f"Error creating empty SQLite database: {str(db_error)}")
        
        return sqlite_path