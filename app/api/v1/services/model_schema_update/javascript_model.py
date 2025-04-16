import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.api.v1.services.model_schema_update.model_schema_base import ModelUpdater

logger = logging.getLogger(__name__)


class JavaScriptModelUpdater(ModelUpdater):
    """Model updater for JavaScript models (Mongoose or Sequelize)"""

    def parse_model_structure(
        self, model_code: str, entity_name: str
    ) -> Dict[str, Any]:
        """
        Parse the structure of a JavaScript model file

        Args:
            model_code: The source code of the model file
            entity_name: The name of the entity being modified

        Returns:
            Dictionary containing the model structure
        """
        # Determine if this is Mongoose or Sequelize
        is_mongoose = "mongoose" in model_code.lower()
        is_sequelize = (
            "sequelize" in model_code.lower() or "datatypes" in model_code.lower()
        )

        structure = {
            "model_type": (
                "mongoose"
                if is_mongoose
                else "sequelize" if is_sequelize else "unknown"
            ),
            "schema_definition": {"start_pos": -1, "end_pos": -1},
            "fields": {},
            "imports": [],
        }

        # Parse imports
        import_regex = re.compile(
            r'(const|let|var|import)\s+([^=;]+)(?:=\s*require\([\'"]([^\'"]+)[\'"]\)|from\s+[\'"]([^\'"]+)[\'"])'
        )
        for match in import_regex.finditer(model_code):
            import_type = match.group(1)
            variable = match.group(2).strip()
            module = match.group(3) or match.group(4)
            structure["imports"].append(
                {
                    "pos": match.start(),
                    "variable": variable,
                    "module": module,
                    "type": import_type,
                }
            )

        if is_mongoose:
            self._parse_mongoose_structure(model_code, entity_name, structure)
        elif is_sequelize:
            self._parse_sequelize_structure(model_code, entity_name, structure)
        else:
            # Generic JS model parsing as fallback
            self._parse_generic_js_structure(model_code, entity_name, structure)

        return structure

    def _parse_mongoose_structure(
        self, model_code: str, entity_name: str, structure: Dict[str, Any]
    ):
        """Parse a Mongoose model structure"""
        # Look for the schema definition
        # Pattern like: const UserSchema = new mongoose.Schema({ ... })
        schema_regex = re.compile(
            r"(?:const|let|var)\s+([A-Za-z0-9_]+Schema)\s*=\s*new\s+mongoose\.Schema\s*\(\s*({[\s\S]*?})[,\s]*(?:\)\s*;|\))",
            re.MULTILINE,
        )

        schema_match = schema_regex.search(model_code)
        if schema_match:
            schema_name = schema_match.group(1)
            schema_content = schema_match.group(2)

            structure["schema_definition"]["start_pos"] = schema_match.start(2)
            structure["schema_definition"]["end_pos"] = schema_match.end(2)
            structure["schema_definition"]["name"] = schema_name
            structure["schema_definition"]["variable_name"] = schema_name

            # Parse fields from the schema content
            # This regex looks for field definitions in the schema object
            field_regex = re.compile(
                r"([A-Za-z0-9_]+)\s*:\s*({[\s\S]*?})(?:,|$)", re.MULTILINE
            )
            for field_match in field_regex.finditer(schema_content):
                field_name = field_match.group(1)
                field_definition = field_match.group(2)

                structure["fields"][field_name] = {
                    "pos": schema_match.start(2) + field_match.start(),
                    "definition": field_definition.strip(),
                }

    def _parse_sequelize_structure(
        self, model_code: str, entity_name: str, structure: Dict[str, Any]
    ):
        """Parse a Sequelize model structure"""
        # Look for the model definition
        # Pattern like: const User = sequelize.define('User', { ... })
        model_regex = re.compile(
            r'(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:sequelize|db)\.define\s*\(\s*[\'"]([^\'"]+)[\'"]\s*,\s*({[\s\S]*?})[,\s]*(?:\)\s*;|\))',
            re.MULTILINE,
        )

        model_match = model_regex.search(model_code)
        if model_match:
            model_var = model_match.group(1)
            model_name = model_match.group(2)
            model_content = model_match.group(3)

            structure["schema_definition"]["start_pos"] = model_match.start(3)
            structure["schema_definition"]["end_pos"] = model_match.end(3)
            structure["schema_definition"]["name"] = model_name
            structure["schema_definition"]["variable_name"] = model_var

            # Parse fields from the model content
            field_regex = re.compile(
                r"([A-Za-z0-9_]+)\s*:\s*({[\s\S]*?})(?:,|$)", re.MULTILINE
            )
            for field_match in field_regex.finditer(model_content):
                field_name = field_match.group(1)
                field_definition = field_match.group(2)

                structure["fields"][field_name] = {
                    "pos": model_match.start(3) + field_match.start(),
                    "definition": field_definition.strip(),
                }

    def _parse_generic_js_structure(
        self, model_code: str, entity_name: str, structure: Dict[str, Any]
    ):
        """Parse a generic JavaScript model structure as fallback"""
        # Look for object definitions that might be models
        object_regex = re.compile(
            r"(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*({[\s\S]*?});", re.MULTILINE
        )

        # Try to find the most likely model object based on the entity name
        entity_variations = [
            entity_name.lower(),
            entity_name.lower() + "s",
            entity_name.lower().rstrip("s"),
            entity_name.lower() + "schema",
            entity_name.lower() + "model",
        ]

        for match in object_regex.finditer(model_code):
            obj_name = match.group(1).lower()
            obj_content = match.group(2)

            if any(variation in obj_name for variation in entity_variations):
                structure["schema_definition"]["start_pos"] = match.start(2)
                structure["schema_definition"]["end_pos"] = match.end(2)
                structure["schema_definition"]["name"] = match.group(1)

                # Parse fields from the object content
                field_regex = re.compile(
                    r"([A-Za-z0-9_]+)\s*:\s*([^,}]+)(?:,|$)", re.MULTILINE
                )
                for field_match in field_regex.finditer(obj_content):
                    field_name = field_match.group(1)
                    field_definition = field_match.group(2)

                    structure["fields"][field_name] = {
                        "pos": match.start(2) + field_match.start(),
                        "definition": field_definition.strip(),
                    }

                break

    def update_model(
        self,
        model_path: Path,
        entity_name: str,
        field_changes: List[Dict[str, Any]],
        existing_model_code: str,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Update a JavaScript model with the specified changes

        Args:
            model_path: Path to the model file
            entity_name: Name of the entity being modified
            field_changes: List of changes to apply
            existing_model_code: Current content of the model file

        Returns:
            Tuple containing updated model code and change summary
        """
        # 1. Parse the model structure
        structure = self.parse_model_structure(existing_model_code, entity_name)

        # 2. Use different update strategies based on model type
        if structure["model_type"] == "mongoose":
            return self._update_mongoose_model(
                structure, field_changes, existing_model_code
            )
        elif structure["model_type"] == "sequelize":
            return self._update_sequelize_model(
                structure, field_changes, existing_model_code
            )
        else:
            # Generic JS model update as fallback
            return self._update_generic_js_model(
                structure, field_changes, existing_model_code
            )

    def _update_mongoose_model(
        self,
        structure: Dict[str, Any],
        field_changes: List[Dict[str, Any]],
        existing_model_code: str,
    ) -> Tuple[str, Dict[str, Any]]:
        """Helper method to update Mongoose models"""
        # Initialize tracking for changes
        added_fields = []
        modified_fields = []
        removed_fields = []
        renamed_fields = []

        # If we couldn't find the schema definition, we can't make changes
        if structure["schema_definition"]["start_pos"] < 0:
            logger.error("Could not find Mongoose schema definition")
            return existing_model_code, {
                "changes_made": False,
                "error": "Could not find Mongoose schema definition",
            }

        updated_code = existing_model_code

        # Process changes in this order: remove, rename, modify, add

        # Step 1: Process remove operations
        for change in field_changes:
            if change["type"].lower() == "remove":
                field_name = change["field_name"]
                if field_name in structure["fields"]:
                    # Get field info
                    field_pos = structure["fields"][field_name]["pos"]
                    field_def = structure["fields"][field_name]["definition"]

                    # Construct a pattern to match the field
                    field_pattern = (
                        re.escape(field_name)
                        + r"\s*:\s*"
                        + re.escape(field_def)
                        + r"\s*,?"
                    )

                    # Search for the field, starting from the known position
                    field_match = re.search(field_pattern, updated_code[field_pos:])

                    if field_match:
                        # Adjust the match positions to be relative to the start of the code
                        start_pos = field_pos + field_match.start()
                        end_pos = field_pos + field_match.end()

                        # Remove the field from the schema
                        updated_code = updated_code[:start_pos] + updated_code[end_pos:]
                        removed_fields.append(field_name)

                        # Update positions for fields that come after this one
                        removed_length = end_pos - start_pos
                        for f_name, f_info in structure["fields"].items():
                            if f_info["pos"] > start_pos:
                                f_info["pos"] -= removed_length
                    else:
                        # We could alternatively use a wider search if the narrow one fails
                        # This is a fallback in case the structure positions are not accurate
                        field_match = re.search(field_pattern, updated_code)
                        if field_match:
                            # Remove the field from the schema
                            updated_code = (
                                updated_code[: field_match.start()]
                                + updated_code[field_match.end() :]
                            )
                            removed_fields.append(field_name)

                            # Update positions for fields that come after this one
                            removed_length = field_match.end() - field_match.start()
                            for f_name, f_info in structure["fields"].items():
                                if f_info["pos"] > field_match.start():
                                    f_info["pos"] -= removed_length
                        else:
                            logger.warning(
                                f"Could not locate field {field_name} in the schema"
                            )
                else:
                    logger.warning(
                        f"Cannot remove field {field_name}: not found in schema"
                    )
        # Step 2: Process rename operations
        for change in field_changes:
            if change["type"].lower() == "rename":
                field_name = change["field_name"]
                new_name = change["new_name"]

                if field_name in structure["fields"]:
                    # Find the field in the schema
                    field_pattern = r"(" + re.escape(field_name) + r")\s*:"
                    field_match = re.search(field_pattern, updated_code)

                    if field_match:
                        # Rename the field
                        updated_code = (
                            updated_code[: field_match.start(1)]
                            + new_name
                            + updated_code[field_match.end(1) :]
                        )
                        renamed_fields.append({"old": field_name, "new": new_name})

                        # Update the structure to reflect the rename
                        structure["fields"][new_name] = structure["fields"][field_name]
                        del structure["fields"][field_name]
                    else:
                        logger.warning(
                            f"Could not locate field {field_name} in the Mongoose schema"
                        )
                else:
                    logger.warning(
                        f"Cannot rename field {field_name}: not found in Mongoose schema"
                    )

        # Step 3: Process modify operations
        for change in field_changes:
            if change["type"].lower() == "modify":
                field_name = change["field_name"]
                if field_name in structure["fields"]:
                    # Find the field in the schema
                    field_def = structure["fields"][field_name]["definition"]
                    field_pattern = (
                        re.escape(field_name)
                        + r"\s*:\s*("
                        + re.escape(field_def)
                        + r")"
                    )
                    field_match = re.search(field_pattern, updated_code)

                    if field_match:
                        # Replace the field definition
                        updated_code = (
                            updated_code[: field_match.start(1)]
                            + change["definition"]
                            + updated_code[field_match.end(1) :]
                        )
                        modified_fields.append(field_name)

                        # Update the structure
                        structure["fields"][field_name]["definition"] = change[
                            "definition"
                        ]
                    else:
                        logger.warning(
                            f"Could not locate field definition for {field_name} in the Mongoose schema"
                        )
                else:
                    logger.warning(
                        f"Cannot modify field {field_name}: not found in Mongoose schema"
                    )

        # Step 4: Process add operations
        for change in field_changes:
            if change["type"].lower() == "add":
                field_name = change["field_name"]

                # Check if the field already exists
                if field_name in structure["fields"]:
                    logger.warning(
                        f"Field {field_name} already exists in Mongoose schema"
                    )
                    continue

                # Find the insertion point - inside the schema object
                schema_start_pos = structure["schema_definition"]["start_pos"]

                # Insert near the beginning of the schema object, right after the opening brace
                insertion_pos = schema_start_pos + 1

                # Prepare the new field entry
                indent = "  "  # Default indentation
                new_field_entry = (
                    f"\n{indent}{field_name}: {change['definition']},\n{indent}"
                )

                # Insert the new field
                updated_code = (
                    updated_code[:insertion_pos]
                    + new_field_entry
                    + updated_code[insertion_pos:]
                )

                # Update positions for fields that come after this one
                added_length = len(new_field_entry)
                for f_name, f_info in structure["fields"].items():
                    if f_info["pos"] > insertion_pos:
                        f_info["pos"] += added_length

                # Add the new field to the structure
                structure["fields"][field_name] = {
                    "pos": insertion_pos + len(indent) + 1,  # +1 for newline
                    "definition": change["definition"],
                }

                added_fields.append(field_name)

        # Create the change summary
        changes_made = (
            len(added_fields)
            + len(modified_fields)
            + len(removed_fields)
            + len(renamed_fields)
            > 0
        )
        change_summary = {
            "changes_made": changes_made,
            "added_fields": added_fields,
            "modified_fields": modified_fields,
            "removed_fields": removed_fields,
            "renamed_fields": renamed_fields,
        }

        return updated_code, change_summary
