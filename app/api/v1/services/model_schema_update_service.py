import difflib
import logging
import re
import shutil
import tempfile
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.api.v1.services.langchain_service import LangchainService

logger = logging.getLogger(__name__)


class FieldChangeType(Enum):
    """Enumeration of possible field change types"""

    ADD = "add"
    MODIFY = "modify"
    REMOVE = "remove"
    RENAME = "rename"


class ModelSchemaManager:
    """
    Comprehensive service for dynamically managing SQLAlchemy models and Pydantic schemas
    based on user requirements.
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
        """
        Process changes to models and schemas based on user prompt

        Args:
            project_id: The project identifier
            entity_name: The model entity name to update
            prompt_description: User's description of the changes needed
            endpoint_code: Optional endpoint code for context
            generate_migration: Whether to generate a migration script
            language: Programming language for the code

        Returns:
            Dictionary containing update results
        """
        try:
            # Get project analysis to find the existing model
            from app.api.v1.services.project_analysis_service import (
                ProjectAnalysisService,
            )

            project_analysis = await ProjectAnalysisService.analyze_project(project_id)
            logger.info(
                f"Project analysis found models: {[m.get('name') for m in project_analysis.get('models', [])]}"
            )

            # Find the model in the project
            entity_variations = [
                entity_name.lower(),
                entity_name.lower() + "s",
                entity_name.lower().rstrip("s"),
            ]

            model_info = None
            for model in project_analysis.get("models", []):
                model_name = model.get("name", "").lower()
                if model_name in entity_variations or any(
                    var == model_name for var in entity_variations
                ):
                    model_info = model
                    logger.info(
                        f"Found matching model: {model_name} for entity: {entity_name}"
                    )
                    break

            if not model_info:
                raise ValueError(f"Model {entity_name} not found in project")

            # Get the model file path
            model_file = f"models/{model_info.get('file')}"
            model_path = Path(f"repos/{project_id}/{model_file}")

            # Read the current model content
            with open(model_path, "r") as f:
                existing_model_code = f.read()

            # Extract required changes using LLM
            field_changes = await ModelSchemaManager.analyze_required_changes(
                prompt_description=prompt_description,
                endpoint_code=endpoint_code,
                entity_name=entity_name,
                existing_model_code=existing_model_code,
                language=language,
            )

            if not field_changes:
                logger.info(f"No changes required for {entity_name} model")
                return {
                    "model_updated": False,
                    "model_file": model_file,
                    "message": "No changes needed",
                    "file_hash": LangchainService.generate_file_hash(
                        existing_model_code
                    ),
                }

            # Update the model file with all changes
            updated_content, change_summary = ModelSchemaManager._update_model_file(
                model_path=model_path,
                entity_name=entity_name,
                field_changes=field_changes,
                existing_model_code=existing_model_code,
            )

            # Create a list of files that need to be committed
            files_to_commit = []
            if change_summary.get("changes_made", False):
                files_to_commit.append(
                    {
                        "file_path": model_file,
                        "commit_message": f"feat: Update {entity_name} model with {len(change_summary.get('added_fields', []))} new fields",
                        "content": updated_content,
                    }
                )

            # Generate migration if requested
            migration_result = None
            if generate_migration and change_summary.get("changes_made", False):
                # Generate migration using updated model code
                migration_result = await LangchainService.generate_migration(
                    project_id=project_id,
                    entity_name=entity_name,
                    language=language,
                    model_code=updated_content,
                )

                # Add migration to files to commit if generated successfully
                if migration_result and "generated_code" in migration_result:
                    logger.info(
                        f"Adding migration to commit: {migration_result.get('file_path')}"
                    )
                    files_to_commit.append(
                        {
                            "file_path": migration_result.get("file_path"),
                            "commit_message": f"feat: Add migration for {entity_name} model changes",
                            "content": migration_result.get("generated_code"),
                        }
                    )

            # Find and update associated schema files
            schema_results = await ModelSchemaManager.update_schemas(
                project_id=project_id,
                entity_name=entity_name,
                field_changes=field_changes,
                model_code=updated_content,
                endpoint_code=endpoint_code,
                language=language,
            )

            # Add schema files to commit list if updated
            if schema_results.get("schema_updated", False):
                for schema_result in schema_results.get("schema_results", []):
                    if schema_result.get("updated", False):
                        # Make sure content is present before adding to commit list
                        schema_content = schema_result.get("content", "")
                        if schema_content:
                            logger.info(
                                f"Adding schema to commit: schemas/{schema_result.get('schema_file')} with {len(schema_content)} bytes"
                            )
                            files_to_commit.append(
                                {
                                    "file_path": f"schemas/{schema_result.get('schema_file')}",
                                    "commit_message": f"feat: Update {entity_name} schemas with new fields",
                                    "content": schema_content,
                                }
                            )
                        else:
                            logger.warning(
                                f"Skipping schema commit for {schema_result.get('schema_file')} - no content available"
                            )

            logger.info(
                f"Prepared {len(files_to_commit)} files to commit: {[f['file_path'] for f in files_to_commit]}"
            )

            return {
                "model_updated": change_summary.get("changes_made", False),
                "model_file": model_file,
                "content_base64": LangchainService.encode_content(updated_content),
                "field_changes": change_summary,
                "file_hash": LangchainService.generate_file_hash(updated_content),
                "migration": migration_result,
                "schema_updated": schema_results.get("schema_updated", False),
                "schema_results": schema_results.get("schema_results", []),
                "files_to_commit": files_to_commit,
            }

        except Exception as e:
            logger.error(f"Error processing model changes: {str(e)}", exc_info=True)
            return {"model_updated": False, "error": str(e)}

    @staticmethod
    async def analyze_required_changes(
        prompt_description: str,
        entity_name: str,
        existing_model_code: str,
        endpoint_code: Optional[str] = None,
        language: str = "python",
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to analyze required model changes based on user prompt

        Returns a list of change operations (add, modify, remove, rename)
        """
        try:
            # Define the prompt template for model changes analysis
            MODEL_CHANGES_TEMPLATE = """
            You are an expert SQLAlchemy developer helping to MODIFY an EXISTING database model.

            TASK: ANALYZE REQUIRED CHANGES TO AN EXISTING MODEL
            You must identify required changes to an existing SQLAlchemy model based on the user's request.

            Entity Name: {entity_name}
            User Request: {prompt_description}

            EXISTING MODEL:
            ```{language}
            {existing_model_code}
            ```

            {endpoint_context}

            INSTRUCTIONS:
            1. Carefully examine the existing model above. This model ALREADY EXISTS in the database.
            2. Analyze the user's request to identify what changes are needed.
            3. Consider all types of changes: adding new fields, modifying existing fields, removing fields, or renaming fields.

            RESPONSE FORMAT:
            Return a JSON array of change operations, where each operation has these fields:
            - "type": The type of change ("add", "modify", "remove", or "rename")
            - "field_name": The name of the field to change
            - "definition": For "add" and "modify", the SQLAlchemy Column definition
            - "new_name": For "rename" operations only, the new field name

            Example:
            [
              {{"type": "add", "field_name": "status", "definition": "Column(Enum(OrderStatus), nullable=False, default=OrderStatus.PROCESSING)"}},
              {{"type": "modify", "field_name": "price", "definition": "Column(Float, nullable=False)"}},
              {{"type": "remove", "field_name": "temporary_field"}},
              {{"type": "rename", "field_name": "customer_name", "new_name": "full_name"}}
            ]

            If no changes are needed, return an empty array: []

            IMPORTANT:
            1. Consider the existing model structure carefully.
            2. Only suggest changes specifically requested or implied by the user.
            3. For renames, include both the old field name and new field name.
            4. For modifications, include the complete new Column definition.
            5. If adding an Enum type, use the existing Enum if one exists in the model, otherwise specify it properly in the Column definition.
            6. Do NOT suggest any changes to standard fields like id, created_at, updated_at.
            """

            # Set up endpoint context if provided
            endpoint_context = ""
            if endpoint_code:
                endpoint_context = f"""
                ENDPOINT CODE:
                ```{language}
                {endpoint_code}
                ```
                """

            # Format the prompt with user's request and existing model
            formatted_prompt = MODEL_CHANGES_TEMPLATE.format(
                entity_name=entity_name,
                prompt_description=prompt_description,
                existing_model_code=existing_model_code,
                endpoint_context=endpoint_context,
                language=language,
            )

            # Create and execute a chain using LangchainService
            chain = LangchainService.create_chain_from_template(formatted_prompt)

            # Execute the chain
            result = await chain.ainvoke({"input": formatted_prompt})

            # Clean the response and parse JSON
            changes_text = LangchainService.clean_code(result)
            changes_text = ModelSchemaManager._clean_json_response(changes_text)

            import json

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
                    if change["field_name"].lower() in [
                        "id",
                        "created_at",
                        "updated_at",
                    ]:
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
    def _clean_json_response(response: str) -> str:
        """
        Clean the LLM response to extract valid JSON
        """
        # Remove markdown code blocks if present
        if "```json" in response or "```" in response:
            # Extract content between code blocks
            import re

            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
            if match:
                return match.group(1).strip()

        # Try to find JSON array in the response
        if response.strip().startswith("[") and response.strip().endswith("]"):
            return response.strip()

        # Look for array pattern in the response
        import re

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

    @staticmethod
    def _update_model_file(
        model_path: Path,
        entity_name: str,
        field_changes: List[Dict[str, Any]],
        existing_model_code: str,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Update a model file with multiple types of field changes

        Returns:
            Tuple of (updated_content, change_summary)
        """
        logger.info(f"Updating model file for {entity_name} at {model_path}")

        # Create a backup of the original content
        backup_path = model_path.with_suffix(".bak")
        with open(backup_path, "w") as f:
            f.write(existing_model_code)
        logger.info(f"Backup created at {backup_path}")

        try:
            # Parse the model to understand its structure
            model_structure = ModelSchemaManager._parse_model_structure(
                existing_model_code, entity_name
            )

            if not model_structure:
                raise ValueError(f"Could not parse model structure for {entity_name}")

            # Create a temporary file for the modifications
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
                temp_file_path = temp_file.name

            # Organize changes by type for easier processing
            changes_by_type = {"add": [], "modify": [], "remove": [], "rename": []}

            for change in field_changes:
                change_type = change["type"].lower()
                if change_type in changes_by_type:
                    changes_by_type[change_type].append(change)

            # Process the file line by line
            with (
                open(model_path, "r") as source_file,
                open(temp_file_path, "w") as target_file,
            ):
                in_model_class = False
                current_line_idx = 0
                found_fields = set()
                processed_renames = set()
                processed_removals = set()

                # State tracking for additions
                additions_inserted = False
                insertion_line_reached = False

                for line in source_file:
                    current_line_idx += 1
                    line_stripped = line.strip()

                    # Check if we're entering the model class
                    if not in_model_class and re.search(
                        f"class\\s+{entity_name}\\s*\\(", line_stripped
                    ):
                        in_model_class = True
                        target_file.write(line)
                        continue

                    # If we're not in the model class, write the line as is
                    if not in_model_class:
                        target_file.write(line)
                        continue

                    # Check if we're exiting the model class (next class or end of file)
                    if in_model_class and (
                        line_stripped.startswith("class ")
                        or current_line_idx == model_structure["class_end_line"]
                    ):
                        # If we haven't inserted additions yet, do it now
                        if not additions_inserted and changes_by_type["add"]:
                            indent = model_structure["indentation"]
                            for add_change in changes_by_type["add"]:
                                field_def = f"{indent}{add_change['field_name']} = {add_change['definition']}\n"
                                target_file.write(field_def)
                            additions_inserted = True

                        in_model_class = False
                        target_file.write(line)
                        continue

                    # Check if this line is a field definition
                    field_match = re.match(r"\s*(\w+)\s*=\s*Column\(", line_stripped)
                    if field_match:
                        field_name = field_match.group(1)
                        found_fields.add(field_name)

                        # Check for modifications
                        modified = False
                        for mod_change in changes_by_type["modify"]:
                            if mod_change["field_name"] == field_name:
                                # Replace with modified definition
                                indent = re.match(r"^(\s*)", line).group(1)
                                modified_line = f"{indent}{field_name} = {mod_change['definition']}\n"
                                target_file.write(modified_line)
                                modified = True
                                break

                        # Check for renames
                        renamed = False
                        if not modified:
                            for rename_change in changes_by_type["rename"]:
                                if (
                                    rename_change["field_name"] == field_name
                                    and field_name not in processed_renames
                                ):
                                    # Write with the new name
                                    indent = re.match(r"^(\s*)", line).group(1)
                                    new_line = line.replace(
                                        f"{field_name} =",
                                        f"{rename_change['new_name']} =",
                                    )
                                    target_file.write(new_line)
                                    renamed = True
                                    processed_renames.add(field_name)
                                    break

                        # Check for removals
                        removed = False
                        if not modified and not renamed:
                            for remove_change in changes_by_type["remove"]:
                                if remove_change["field_name"] == field_name:
                                    # Skip this line to remove the field
                                    removed = True
                                    processed_removals.add(field_name)
                                    break

                        # If not modified, renamed, or removed, write the original line
                        if not modified and not renamed and not removed:
                            target_file.write(line)

                        continue

                    # Check if we're at the insertion point for additions
                    if in_model_class and not additions_inserted:
                        # Common insertion points
                        if (
                            current_line_idx == model_structure["fields_end_line"]
                            or current_line_idx == model_structure["insertion_line"]
                        ):
                            insertion_line_reached = True

                        # If we've reached the right spot and have new fields to add
                        if insertion_line_reached and changes_by_type["add"]:
                            indent = model_structure["indentation"]
                            for add_change in changes_by_type["add"]:
                                field_def = f"{indent}{add_change['field_name']} = {add_change['definition']}\n"
                                target_file.write(field_def)
                            additions_inserted = True

                    # Write the line for all other content
                    target_file.write(line)

            # Move the temp file to replace the original
            shutil.move(temp_file_path, model_path)

            # Read the updated content
            with open(model_path, "r") as f:
                updated_content = f.read()

            # Build a change summary
            change_summary = {
                "changes_made": bool(
                    changes_by_type["add"]
                    or changes_by_type["modify"]
                    or changes_by_type["remove"]
                    or changes_by_type["rename"]
                ),
                "added_fields": [
                    change["field_name"] for change in changes_by_type["add"]
                ],
                "modified_fields": [
                    change["field_name"] for change in changes_by_type["modify"]
                ],
                "removed_fields": [
                    change["field_name"] for change in changes_by_type["remove"]
                ],
                "renamed_fields": [
                    {"old_name": change["field_name"], "new_name": change["new_name"]}
                    for change in changes_by_type["rename"]
                ],
                "diff": ModelSchemaManager._generate_diff(
                    existing_model_code, updated_content
                ),
            }

            logger.info(f"Successfully updated model file: {change_summary}")
            return updated_content, change_summary

        except Exception as e:
            logger.error(f"Error updating model file: {str(e)}", exc_info=True)
            # Restore from backup
            try:
                shutil.copy(backup_path, model_path)
                logger.info("Restored from backup after error")
            except Exception as restore_err:
                logger.error(f"Error restoring from backup: {str(restore_err)}")

            raise

    @staticmethod
    def _parse_model_structure(model_code: str, entity_name: str) -> Dict[str, Any]:
        """
        Parse the structure of a model to identify key positions
        """
        lines = model_code.split("\n")
        result = {
            "class_start_line": -1,
            "class_end_line": len(lines),
            "fields_start_line": -1,
            "fields_end_line": -1,
            "insertion_line": -1,
            "indentation": "    ",
            "existing_fields": {},
        }

        # Find the class definition
        for i, line in enumerate(lines):
            if re.search(f"class\\s+{entity_name}\\s*\\(", line.strip()):
                result["class_start_line"] = i
                break

        if result["class_start_line"] == -1:
            logger.error(f"Could not find class definition for {entity_name}")
            return None

        # Find field definitions and determine indentation
        in_field_section = False
        field_pattern = re.compile(r"\s*(\w+)\s*=\s*Column\(")

        for i in range(result["class_start_line"] + 1, len(lines)):
            line = lines[i].strip()

            # Check for next class definition or end of file
            if line.startswith("class ") or i == len(lines) - 1:
                result["class_end_line"] = i
                if in_field_section:
                    result["fields_end_line"] = i - 1
                break

            # Extract indentation
            if line and result["indentation"] == "    ":
                match = re.match(r"^(\s+)", lines[i])
                if match:
                    result["indentation"] = match.group(1)

            # Check for field definitions
            field_match = field_pattern.match(lines[i])
            if field_match:
                if not in_field_section:
                    in_field_section = True
                    result["fields_start_line"] = i

                field_name = field_match.group(1)
                result["existing_fields"][field_name] = i
            elif in_field_section and (line.startswith("def ") or not line):
                # End of field section when we hit a method or blank line
                result["fields_end_line"] = i - 1
                in_field_section = False

        # Determine the best insertion line for new fields
        # Priority: After timestamps but before relationships
        has_timestamps = (
            "created_at" in result["existing_fields"]
            or "updated_at" in result["existing_fields"]
        )

        if has_timestamps:
            timestamp_lines = []
            if "created_at" in result["existing_fields"]:
                timestamp_lines.append(result["existing_fields"]["created_at"])
            if "updated_at" in result["existing_fields"]:
                timestamp_lines.append(result["existing_fields"]["updated_at"])

            result["insertion_line"] = max(timestamp_lines) + 1
        else:
            # If no timestamps, insert at the end of fields or after id
            if result["fields_end_line"] != -1:
                result["insertion_line"] = result["fields_end_line"] + 1
            elif "id" in result["existing_fields"]:
                result["insertion_line"] = result["existing_fields"]["id"] + 1
            else:
                # Fallback: insert after class definition
                result["insertion_line"] = result["class_start_line"] + 1

        # If we haven't explicitly found the end of fields, set it to class end
        if result["fields_end_line"] == -1:
            result["fields_end_line"] = result["class_end_line"] - 1

        return result

    @staticmethod
    async def update_schemas(
        project_id: str,
        entity_name: str,
        field_changes: List[Dict[str, Any]],
        model_code: str,
        endpoint_code: Optional[str] = None,
        language: str = "python",
    ) -> Dict[str, Any]:
        """
        Update schemas associated with a model after changes
        """
        try:
            # Get project analysis to find associated schemas
            from app.api.v1.services.project_analysis_service import (
                ProjectAnalysisService,
            )

            project_analysis = await ProjectAnalysisService.analyze_project(project_id)

            # Find schemas related to the entity
            schema_files = []
            for schema in project_analysis.get("schemas", []):
                schema_name = schema.get("name", "")
                if entity_name.lower() in schema_name.lower():
                    schema_files.append(schema.get("file"))

            if not schema_files:
                logger.warning(f"No schemas found for {entity_name}")
                return {"schema_updated": False, "reason": "No schemas found"}

            # Convert SQLAlchemy field changes to Pydantic field changes
            pydantic_changes = ModelSchemaManager._convert_to_pydantic_changes(
                field_changes
            )

            results = []
            schema_updated = False

            # Update each schema file
            for schema_file in schema_files:
                schema_path = Path(f"repos/{project_id}/schemas/{schema_file}")

                # Skip if file doesn't exist
                if not schema_path.exists():
                    results.append(
                        {
                            "schema_file": schema_file,
                            "updated": False,
                            "reason": "File not found",
                        }
                    )
                    continue

                # Create a backup of the original schema
                with open(schema_path, "r") as f:
                    original_schema = f.read()

                backup_path = schema_path.with_suffix(".bak")
                with open(backup_path, "w") as f:
                    f.write(original_schema)

                try:
                    # Find all schema classes related to the entity
                    schema_classes = ModelSchemaManager._find_schema_classes(
                        original_schema, entity_name
                    )

                    if not schema_classes:
                        results.append(
                            {
                                "schema_file": schema_file,
                                "updated": False,
                                "reason": "No relevant schema classes found",
                            }
                        )
                        continue

                    # Update each schema class
                    updated_schema = original_schema
                    updated = False

                    for class_info in schema_classes:
                        result = ModelSchemaManager._update_schema_class(
                            schema_content=updated_schema,
                            class_name=class_info["name"],
                            line_range=class_info["line_range"],
                            schema_type=class_info.get("schema_type", "unknown"),
                            field_changes=pydantic_changes,
                        )

                        if result["updated"]:
                            updated_schema = result["content"]
                            updated = True

                    # Only write back if changes were made
                    if updated:
                        with open(schema_path, "w") as f:
                            f.write(updated_schema)

                        schema_updated = True
                        results.append(
                            {
                                "schema_file": schema_file,
                                "updated": True,
                                "content": updated_schema,
                                "diff": ModelSchemaManager._generate_diff(
                                    original_schema, updated_schema
                                ),
                                "class_count": len(schema_classes),
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

                except Exception as e:
                    logger.error(
                        f"Error updating schema {schema_file}: {str(e)}", exc_info=True
                    )
                    # Restore from backup
                    with open(schema_path, "w") as f:
                        f.write(original_schema)

                    results.append(
                        {"schema_file": schema_file, "updated": False, "error": str(e)}
                    )

            return {"schema_updated": schema_updated, "schema_results": results}

        except Exception as e:
            logger.error(f"Error updating schemas: {str(e)}", exc_info=True)
            return {"schema_updated": False, "error": str(e)}

    @staticmethod
    def _find_schema_classes(
        schema_content: str, entity_name: str
    ) -> List[Dict[str, Any]]:
        """
        Find schema classes related to an entity with type detection
        """
        classes = []
        lines = schema_content.split("\n")

        # Regex patterns for class definitions and type hints
        class_pattern = re.compile(r"class\s+(\w+)")
        base_class_pattern = re.compile(r"class\s+\w+\((\w+)")

        current_class = None
        start_line = None

        for i, line in enumerate(lines):
            # Check for class definition
            match = class_pattern.search(line)
            if match:
                # If we were tracking a class, add it to the list
                if current_class and start_line is not None:
                    if entity_name.lower() in current_class.lower():
                        # Determine schema type
                        schema_type = "unknown"

                        # Look back at the class definition to determine type
                        for j in range(start_line, min(start_line + 5, i)):
                            base_match = base_class_pattern.search(lines[j])
                            if base_match:
                                base_class = base_match.group(1).lower()
                                if "base" in base_class:
                                    schema_type = "base"
                                elif "create" in base_class:
                                    schema_type = "create"
                                elif "update" in base_class:
                                    schema_type = "update"
                                elif "response" in base_class:
                                    schema_type = "response"
                                break

                        classes.append(
                            {
                                "name": current_class,
                                "line_range": (start_line, i),
                                "schema_type": schema_type,
                            }
                        )

                # Start tracking a new class
                current_class = match.group(1)
                start_line = i

        # Add the last class if it exists
        if current_class and start_line is not None:
            if entity_name.lower() in current_class.lower():
                # Determine schema type for the last class
                schema_type = "unknown"
                for j in range(start_line, min(start_line + 5, len(lines))):
                    base_match = base_class_pattern.search(lines[j])
                    if base_match:
                        base_class = base_match.group(1).lower()
                        if "base" in base_class:
                            schema_type = "base"
                        elif "create" in base_class:
                            schema_type = "create"
                        elif "update" in base_class:
                            schema_type = "update"
                        elif "response" in base_class:
                            schema_type = "response"
                        break

                classes.append(
                    {
                        "name": current_class,
                        "line_range": (start_line, len(lines)),
                        "schema_type": schema_type,
                    }
                )

        return classes

    @staticmethod
    def _generate_diff(original: str, modified: str, context_lines: int = 3) -> str:
        """
        Generate a unified diff between original and modified content
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
