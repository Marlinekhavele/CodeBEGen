import difflib
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.api.v1.services.langchain_service import LangchainService
from app.api.v1.services.language_templates import LanguageTemplateFactory
from app.api.v1.services.language_templates.python_template import PythonTemplate
from app.api.v1.services.model_schema_update.model_schema_base import (
    ModelSchemaManagerFactory,
)
from app.api.v1.services.project_analysis_service import ProjectAnalysisService
from app.api.v1.utils.prompt_manager import PromptManager

logger = logging.getLogger(__name__)


class ModelSchemaManager:
    """
    Comprehensive service for dynamically managing database models and validation schemas
    across multiple programming languages.
    """

    @staticmethod
    async def process_model_changes(
        project_id: str,
        entity_name: str,
        prompt_description: str,
        endpoint_code: Optional[str] = None,
        generate_migration: bool = True,
        language: str = "python",
    ) -> Optional[Dict[str, Any]]:
        try:
            # Get language template
            language_template = LanguageTemplateFactory.get_template(language)

            # Get project analysis
            project_analysis = await ProjectAnalysisService.analyze_project(
                project_id, language=language
            )

            # Find the model in the project
            model_info = ModelSchemaManager._find_matching_model(
                project_analysis, entity_name, language
            )

            if not model_info:
                raise ValueError(f"Model {entity_name} not found in project")

            # Get the model file path using the language template
            model_file, model_path = ModelSchemaManager._get_model_file_path(
                project_id, entity_name, model_info, language_template, language
            )

            # Read the current model content
            with open(model_path, "r") as f:
                existing_model_code = (
                    f.read()
                )  # Use LLM to identify needed field changes
            field_changes = await ModelSchemaManager.analyze_required_changes(
                prompt_description,
                entity_name,
                existing_model_code,
                endpoint_code,
                language,
            )

            # Get model updater for this language
            model_updater = ModelSchemaManagerFactory.get_model_updater(language)

            # Update the model
            updated_content, change_summary = model_updater.update_model(
                model_path, entity_name, field_changes, existing_model_code
            )

            # Update the model file
            ModelSchemaManager._update_model_file(
                model_path, updated_content, project_id
            )

            # Initialize result to track file changes
            files_to_commit = []
            result = {
                "model_updated": change_summary.get("changes_made", False),
                "content_base64": LangchainService.encode_content(updated_content),
                "file_hash": LangchainService.generate_file_hash(updated_content),
                "model_file": model_file,
                "field_changes": change_summary,
            }

            if change_summary.get("changes_made", False):
                # Add model to files to commit
                files_to_commit.append(
                    {
                        "file_path": model_file,
                        "commit_message": f"feat: Update {entity_name} model with {len(change_summary.get('added_fields', []))} new fields",
                        "content": updated_content,
                    }
                )

                # Generate migration if requested and changes were made
                if generate_migration and language.lower() == "python":
                    try:
                        # Use the new Alembic autogenerate-based migration logic
                        migration_result = await language_template.generate_migration(
                            project_dir=Path(f"repos/{project_id}"),
                            entity_name=entity_name,
                        )
                        # Add migration file(s) to files_to_commit if present
                        if migration_result and "migration_files" in migration_result:
                            for file_info in migration_result["migration_files"]:
                                files_to_commit.append(file_info)
                        # Add migration component to result if present
                        if (
                            migration_result
                            and "migration_component" in migration_result
                        ):
                            result["migration"] = migration_result[
                                "migration_component"
                            ]
                        result["migration_status"] = "success"
                    except Exception as e:
                        logger.error(f"Error generating migration: {str(e)}")
                        result["migration_status"] = "failed"
                        result["migration_error"] = str(e)

                # Update schemas if needed
                schema_results = await ModelSchemaManager._update_schemas(
                    project_id,
                    entity_name,
                    field_changes,
                    updated_content,
                    endpoint_code,
                    language,
                    language_template,
                )

                # Add schema files to commit list if updated
                if schema_results.get("schema_updated", False):
                    for schema_result in schema_results.get("schema_results", []):
                        if schema_result.get("updated", False) and schema_result.get(
                            "content"
                        ):
                            schema_file_path = ModelSchemaManager._get_schema_file_path(
                                project_id,
                                entity_name,
                                schema_result.get("schema_file", ""),
                                language,
                                language_template,
                            )
                            files_to_commit.append(
                                {
                                    "file_path": schema_file_path,
                                    "commit_message": f"feat: Update {entity_name} schemas with new fields",
                                    "content": schema_result.get("content"),
                                }
                            )

                # Add files to commit to the result
                result["files_to_commit"] = files_to_commit
                result["schema_results"] = schema_results

            return result

        except Exception as e:
            logger.error(f"Error in process_model_changes: {str(e)}", exc_info=True)
            return {
                "error": str(e),
                "model_updated": False,
            }

    @staticmethod
    def _update_model_file(
        model_path: Path, updated_content: str, project_id: str = None
    ) -> None:
        """
        Update a model file with new content. Ensures the file is written inside repos/{project_id}/.

        Args:
            model_path (Path): Path to the model file (can be relative)
            updated_content (str): New content to write to the file
            project_id (str, optional): Project ID for absolute path resolution
        """
        # Ensure model_path is absolute and inside repos/{project_id}/
        if project_id and not str(model_path).replace("\\", "/").startswith(
            f"repos/{project_id}/"
        ):
            model_path = Path(f"repos/{project_id}") / model_path
        model_path.parent.mkdir(parents=True, exist_ok=True)
        with open(model_path, "w") as f:
            f.write(updated_content)

    @staticmethod
    def _find_matching_model(
        project_analysis: Dict[str, Any], entity_name: str, language: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find a matching model in the project analysis.

        Args:
            project_analysis (Dict[str, Any]): Analysis of the project.
            entity_name (str): Name of the entity.
            language (str): Programming language.

        Returns:
            Optional[Dict[str, Any]]: Matching model info or None.
        """
        # Try variations of the entity name
        entity_variations = [
            entity_name.lower(),
            entity_name.lower() + "s",
            entity_name.lower().rstrip("s"),
        ]

        for model in project_analysis.get("models", []):
            model_name = model.get("name", "").lower()
            if model_name in entity_variations or any(
                var == model_name for var in entity_variations
            ):
                logger.info(
                    f"Found matching model: {model_name} for entity: {entity_name}"
                )
                return model

        return None

    @staticmethod
    def _get_model_file_path(
        project_id: str,
        entity_name: str,
        model_info: Dict[str, Any],
        language_template: Any,
        language: str,
    ) -> Tuple[str, Path]:
        """
        Get the file path for a model.

        Args:
            project_id (str): Project identifier.
            entity_name (str): Name of the entity.
            model_info (Dict[str, Any]): Model information.
            language_template (Any): Language template.
            language (str): Programming language.

        Returns:
            Tuple[str, Path]: Model file and its path.
        """
        # Get component path from language template
        component_map = language_template.get_component_map()
        model_component = component_map.get("model")
        component_paths = language_template.get_component_paths(project_id, entity_name)

        # Try language-specific path first
        model_file = component_paths[model_component]
        model_path = Path(f"repos/{project_id}/{model_file}")

        # If path doesn't exist but we have model info with a file, try that
        if not model_path.exists() and model_info and "file" in model_info:
            language_prefix = ""
            if language.lower() == "python":
                language_prefix = "python/"
            elif language.lower() in ["javascript", "js"]:
                language_prefix = "javascript/"

            # Try with language prefix
            model_file = f"{language_prefix}models/{model_info.get('file')}"
            model_path = Path(f"repos/{project_id}/{model_file}")

            # If still doesn't exist, try without language prefix
            if not model_path.exists():
                model_file = f"models/{model_info.get('file')}"
                model_path = Path(f"repos/{project_id}/{model_file}")

        return model_file, model_path

    @staticmethod
    def _get_schema_file_path(
        project_id: str,
        entity_name: str,
        schema_file: str,
        language: str,
        language_template: Any,
    ) -> str:
        """
        Get the file path for a schema.

        Args:
            project_id (str): Project identifier.
            entity_name (str): Name of the entity.
            schema_file (str): Schema file name.
            language (str): Programming language.
            language_template (Any): Language template.

        Returns:
            str: Schema file path.
        """
        # Get component path from language template
        component_map = language_template.get_component_map()
        schema_component = component_map.get("schema")

        if not schema_component:
            # This language doesn't use separate schema files
            return schema_file

        # Try language-specific path
        component_paths = language_template.get_component_paths(project_id, entity_name)
        schema_file_path = component_paths[schema_component]

        # Check if the path exists
        schema_path = Path(f"repos/{project_id}/{schema_file_path}")
        if schema_path.exists():
            return schema_file_path

        # Try with language prefix
        language_prefix = ""
        if language.lower() == "python":
            language_prefix = "python/"
        elif language.lower() in ["javascript", "js"]:
            language_prefix = "javascript/"

        schema_file_path = f"{language_prefix}schemas/{schema_file}"
        schema_path = Path(f"repos/{project_id}/{schema_file_path}")

        # If still doesn't exist, try without language prefix
        if not schema_path.exists():
            schema_file_path = f"schemas/{schema_file}"

        return schema_file_path @ staticmethod

    async def _generate_migration(
        project_id: str, entity_name: str, language: str, model_code: str
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a migration for model changes using Alembic autogenerate.

        Args:
            project_id (str): Project identifier.
            entity_name (str): Name of the entity.
            language (str): Programming language.
            model_code (str): Updated model code.

        Returns:
            Optional[Dict[str, Any]]: Migration result or None.
        """
        try:
            # Use PythonTemplate.generate_migration for proper Alembic autogenerate
            if language.lower() == "python":
                project_dir = f"repos/{project_id}"
                python_template = PythonTemplate()
                migration_result = await python_template.generate_migration(
                    project_dir=project_dir, entity_name=entity_name
                )

                # Return migration result in expected format
                if migration_result.get("migration_status") == "success":
                    return migration_result
                else:
                    logger.error(
                        f"Migration generation failed: {migration_result.get('error', 'Unknown error')}"
                    )
                    return None
            else:
                # For non-Python languages, fall back to LLM generation
                logger.warning(
                    f"Using LLM migration generation for language: {language}"
                )
                return await LangchainService.generate_migration(
                    project_id=project_id,
                    entity_name=entity_name,
                    language=language,
                    model_code=model_code,
                )
        except Exception as e:
            logger.error(f"Error generating migration: {str(e)}", exc_info=True)
            return None

    @staticmethod
    async def _update_schemas(
        project_id: str,
        entity_name: str,
        field_changes: List[Dict[str, Any]],
        model_code: str,
        endpoint_code: Optional[str],
        language: str,
        language_template: Any,
    ) -> Dict[str, Any]:
        """
        Update schemas related to a model.

        Args:
            project_id (str): Project identifier.
            entity_name (str): Name of the entity.
            field_changes (List[Dict[str, Any]]): List of field changes.
            model_code (str): Updated model code.
            endpoint_code (Optional[str]): Endpoint code for context.
            language (str): Programming language.
            language_template (Any): Language template.

        Returns:
            Dict[str, Any]: Schema update results.
        """
        try:
            # Check if this language supports schemas
            component_map = language_template.get_component_map()
            schema_component = component_map.get("schema")

            if not schema_component:
                logger.info(f"Language {language} does not use separate schema files")
                return {
                    "schema_updated": False,
                    "reason": "Language does not use schemas",
                }

            # Analyze the project
            project_analysis = await ProjectAnalysisService.analyze_project(
                project_id, language=language
            )
            schemas_entries = project_analysis.get("schemas", [])
            logger.debug(f"Found {len(schemas_entries)} schemas in project analysis")
            # Find schemas related to the entity
            schema_files, schema_types = ModelSchemaManager._find_related_schemas(
                project_analysis, entity_name, language
            )
            if not schema_files:
                logger.warning(f"No schemas found for {entity_name}")
                return {"schema_updated": False, "reason": "No schemas found"}

            # Process each schema file
            results = []
            schema_updated = False

            for i, schema_file in enumerate(schema_files):
                schema_type = schema_types.get(schema_file, None)
                schema_path = ModelSchemaManager._get_schema_file_path_object(
                    project_id, entity_name, schema_file, language, language_template
                )

                # Skip if file doesn't exist
                if not schema_path or not schema_path.exists():
                    results.append(
                        {
                            "schema_file": schema_file,
                            "updated": False,
                            "reason": "File not found",
                        }
                    )
                    continue

                # Read the schema content
                with open(schema_path, "r") as f:
                    schema_content = f.read()

                # Get the appropriate schema updater
                schema_updater = ModelSchemaManagerFactory.get_schema_updater(
                    language, schema_type
                )

                # Convert model changes to schema changes
                schema_changes = schema_updater.convert_model_changes_to_schema_changes(
                    field_changes
                )

                # Find schemas in the content
                schemas = schema_updater.find_schemas(schema_content, entity_name)

                if not schemas:
                    results.append(
                        {
                            "schema_file": schema_file,
                            "updated": False,
                            "reason": "No relevant schemas found",
                        }
                    )
                    continue

                # Update each schema
                updated_content = schema_content
                updated = False

                for schema_info in schemas:
                    result = schema_updater.update_schema(
                        updated_content, schema_info, schema_changes
                    )

                    if result["updated"]:
                        updated_content = result["content"]
                        updated = True

                # Only write back if changes were made
                if updated:
                    # Ensure schema_path is absolute and inside repos/{project_id}/
                    if (
                        not str(schema_path)
                        .replace("\\", "/")
                        .startswith(f"repos/{project_id}/")
                    ):
                        schema_path = Path(f"repos/{project_id}") / schema_path
                    schema_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(schema_path, "w") as f:
                        f.write(updated_content)

                    schema_updated = True
                    results.append(
                        {
                            "schema_file": schema_file,
                            "updated": True,
                            "content": updated_content,
                            "diff": ModelSchemaManager._generate_diff(
                                schema_content, updated_content
                            ),
                            "schema_count": len(schemas),
                        }
                    )
                else:
                    results.append(
                        {
                            "schema_file": schema_file,
                            "updated": False,
                            "reason": "No changes needed",
                        }
                    )

            return {"schema_updated": schema_updated, "schema_results": results}

        except Exception as e:
            logger.error(f"Error updating schemas: {str(e)}", exc_info=True)
            return {"schema_updated": False, "error": str(e)}

    @staticmethod
    def _find_related_schemas(
        project_analysis: Dict[str, Any], entity_name: str, language: str
    ) -> Tuple[List[str], Dict[str, str]]:
        """
        Find schemas related to an entity.

        Args:
            project_analysis (Dict[str, Any]): Project analysis.
            entity_name (str): Name of the entity.
            language (str): Programming language.

        Returns:
            Tuple[List[str], Dict[str, str]]: List of schema files and their types.
        """
        schema_files = []
        schema_types = {}  # Map file to schema type

        # Look in schemas
        for schema in project_analysis.get("schemas", []):
            schema_name = schema.get("name", "")
            schema_file = schema.get("file", "")
            schema_type = schema.get("type", "unknown")

            # Match schemas that might be related to our entity
            if entity_name.lower() in schema_name.lower():
                schema_files.append(schema_file)
                schema_types[schema_file] = schema_type

        # For JavaScript, also look in utils for validation files
        if language.lower() in ["javascript", "js"]:
            for helper in project_analysis.get("helpers", []):
                helper_file = helper.get("file", "")
                if (
                    "validation" in helper_file.lower()
                    or entity_name.lower() in helper_file.lower()
                ):
                    schema_files.append(helper_file)
                    # Try to determine type from file name
                    if "joi" in helper_file.lower():
                        schema_types[helper_file] = "joi"
                    elif "validator" in helper_file.lower():
                        schema_types[helper_file] = "express-validator"
                    else:
                        schema_types[helper_file] = "unknown"

        return schema_files, schema_types

    @staticmethod
    def _get_schema_file_path_object(
        project_id: str,
        entity_name: str,
        schema_file: str,
        language: str,
        language_template: Any,
    ) -> Optional[Path]:
        """
        Get a Path object for a schema file.

        Args:
            project_id (str): Project identifier.
            entity_name (str): Name of the entity.
            schema_file (str): Schema file name.
            language (str): Programming language.
            language_template (Any): Language template.

        Returns:
            Optional[Path]: Path object for the schema file.
        """
        # Convert string path to Path object
        schema_file_path = ModelSchemaManager._get_schema_file_path(
            project_id, entity_name, schema_file, language, language_template
        )

        return Path(f"repos/{project_id}/{schema_file_path}")

    @staticmethod
    def _generate_diff(original: str, modified: str, context_lines: int = 3) -> str:
        """
        Generate a unified diff between original and modified content.

        Args:
            original (str): Original content.
            modified (str): Modified content.
            context_lines (int, optional): Number of context lines.

        Returns:
            str: Unified diff string.
        """
        original_lines = original.splitlines(True)
        modified_lines = modified.splitlines(True)

        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile="original",
            tofile="modified",
            n=context_lines,
        )

        return "".join(diff)

    @staticmethod
    async def analyze_required_changes(
        prompt_description: str,
        entity_name: str,
        existing_model_code: str,
        endpoint_code: Optional[str] = None,
        language: str = "python",
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to analyze required model changes based on user prompt.

        Args:
            prompt_description (str): User's prompt describing the changes.
            entity_name (str): Name of the entity.
            existing_model_code (str): Existing model code.
            endpoint_code (Optional[str], optional): Endpoint code for context.
            language (str, optional): Programming language.

        Returns:
            List[Dict[str, Any]]: List of validated changes.
        """
        try:
            # Set up endpoint context if provided
            endpoint_context = ""
            if endpoint_code:
                endpoint_context = f"""
                ENDPOINT CODE:
                ```{language}
                {endpoint_code}
                ```
                """

            # Use PromptManager to get and format the template
            # Get the appropriate template name based on language
            template_name = "model_changes"

            # Format the template using PromptManager - avoid passing language twice
            formatted_prompt = PromptManager.format_template(
                template_name=template_name,
                language=language,
                entity_name=entity_name,
                prompt_description=prompt_description,
                existing_model_code=existing_model_code,
                endpoint_context=endpoint_context,
            )

            # Create and execute a chain using LangchainService
            chain = LangchainService.create_chain_from_template(formatted_prompt)

            # Execute the chain
            result = await chain.ainvoke({"input": formatted_prompt})

            # Clean the response and parse JSON
            changes_text = LangchainService.clean_code(result)
            changes_text = ModelSchemaManager._clean_json_response(changes_text)

            try:
                changes = json.loads(changes_text)
                logger.info(
                    f"Parsed {len(changes)} change operations for {entity_name}"
                )

                # Validate the changes
                validated_changes = []
                for change in changes:
                    if "type" not in change or "field_name" not in change:
                        logger.warning(f"Skipping invalid change operation: {change}")
                        continue

                    change_type = change["type"].lower()

                    # Validate by type
                    if change_type == "add" or change_type == "modify":
                        if "definition" not in change:
                            logger.warning(
                                f"Skipping {change_type} operation missing definition: {change}"
                            )
                            continue
                    elif change_type == "rename":
                        if "new_name" not in change:
                            logger.warning(
                                f"Skipping rename operation missing new_name: {change}"
                            )
                            continue
                    elif change_type != "remove":
                        logger.warning(
                            f"Skipping unknown operation type: {change_type}"
                        )
                        continue

                    # Skip standard fields
                    standard_fields = ModelSchemaManager._get_standard_fields(language)
                    if change["field_name"].lower() in standard_fields:
                        logger.warning(
                            f"Skipping change to standard field: {change['field_name']}"
                        )
                        continue

                    validated_changes.append(change)

                return validated_changes
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                logger.error(f"Raw response: {changes_text}")
                return []

        except Exception as e:
            logger.error(f"Error analyzing model changes: {str(e)}", exc_info=True)
            return []

    @staticmethod
    def _get_standard_fields(language: str) -> List[str]:
        """
        Get standard fields that shouldn't be modified.

        Args:
            language (str): Programming language.

        Returns:
            List[str]: List of standard field names.
        """
        if language.lower() == "python":
            return ["id", "created_at", "updated_at"]
        elif language.lower() in ["javascript", "js"]:
            return ["_id", "id", "createdat", "updatedat", "created_at", "updated_at"]
        else:
            return ["id", "created_at", "updated_at"]

    @staticmethod
    def _clean_json_response(response: str) -> str:
        """
        Clean the LLM response to extract valid JSON.

        Args:
            response (str): LLM response.

        Returns:
            str: Cleaned JSON string.
        """
        # Remove markdown code blocks if present
        if "```json" in response or "```" in response:
            # Extract content between code blocks
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
            if match:
                return match.group(1).strip()

        # Try to find JSON array in the response
        if response.strip().startswith("[") and response.strip().endswith("]"):
            return response.strip()

        # Look for array pattern in the response
        match = re.search(r"(\[\s*{.*}\s*\])", response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Handle the case where a JSON array is at the end of the text
        match = re.search(
            r".*?((?:\[\s*\])|(?:\[\s*{.*?}\s*(?:,\s*{.*?}\s*)*\]))",
            response,
            re.DOTALL,
        )
        if match:
            return match.group(1).strip()

        # If response contains an empty array statement
        if "[]" in response:
            return "[]"

        # As a final fallback, if we can't find a JSON array but have a clear indication it should be empty
        if re.search(r"no changes|empty array", response, re.IGNORECASE):
            return "[]"

        return response.strip()
