import logging
import re
from typing import Any, Dict, List

from app.api.v1.services.model_schema_update.model_schema_base import SchemaUpdater

logger = logging.getLogger(__name__)

#
# CONCRETE SHEMA UPDATER IMPLEMENTATIONS
#


class PydanticSchemaUpdater(SchemaUpdater):
    """Schema updater for Python Pydantic schemas"""

    def find_schemas(
        self, schema_content: str, entity_name: str
    ) -> List[Dict[str, Any]]:
        """
        Find Pydantic schemas related to an entity in the content

        Args:
            schema_content: Content of the schema file
            entity_name: Entity name to search for

        Returns:
            List of schema information dictionaries
        """
        schemas = []

        # Compile regex patterns to find Pydantic model classes
        class_pattern = re.compile(
            r"class\s+([A-Za-z0-9_]+)\s*\(\s*[A-Za-z0-9_.]+\s*\)\s*:", re.MULTILINE
        )

        # Entity name variations to search for
        entity_variations = [
            entity_name.lower(),
            entity_name.lower() + "create",
            entity_name.lower() + "update",
            entity_name.lower() + "response",
            entity_name.lower() + "in",
            entity_name.lower() + "out",
            entity_name.lower() + "base",
            entity_name.lower() + "schema",
            entity_name.lower() + "dto",
        ]

        # Find all class definitions
        for match in class_pattern.finditer(schema_content):
            class_name = match.group(1)

            # Check if this class is related to our entity
            if any(variation in class_name.lower() for variation in entity_variations):
                # Found a relevant schema
                class_start = match.start()

                # Find the end of the class by indentation
                lines = schema_content.splitlines()
                class_line_num = schema_content[:class_start].count("\n")

                # Get the indentation of the class definition
                if class_line_num < len(lines):
                    class_line = lines[class_line_num]
                    class_indent = len(class_line) - len(class_line.lstrip())

                    # Find the end of the class
                    class_end = len(schema_content)
                    for i in range(class_line_num + 1, len(lines)):
                        if (
                            lines[i].strip()
                            and len(lines[i]) - len(lines[i].lstrip()) <= class_indent
                        ):
                            # This line has same or less indentation, so it's outside the class
                            class_end = sum(len(line) + 1 for line in lines[:i])
                            break

                    # Now find field definitions within the class
                    field_pattern = re.compile(
                        r"^\s+([A-Za-z0-9_]+)\s*(?::|=)", re.MULTILINE
                    )
                    fields = {}

                    class_content = schema_content[class_start:class_end]
                    for field_match in field_pattern.finditer(class_content):
                        field_name = field_match.group(1)

                        # Skip special fields
                        if field_name.startswith("__") or field_name in [
                            "Config",
                            "schema_extra",
                        ]:
                            continue

                        field_pos = class_start + field_match.start()
                        field_line = schema_content[:field_pos].count("\n")

                        # Extract the field definition
                        if field_line < len(lines):
                            field_line_content = lines[field_line]
                            field_def = field_line_content.strip()

                            fields[field_name] = {
                                "pos": field_pos,
                                "line": field_line,
                                "definition": field_def,
                            }

                    schemas.append(
                        {
                            "name": class_name,
                            "start_pos": class_start,
                            "end_pos": class_end,
                            "fields": fields,
                        }
                    )

        return schemas

    def update_schema(
        self,
        schema_content: str,
        schema_info: Dict[str, Any],
        field_changes: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Update a Pydantic schema with the specified changes

        Args:
            schema_content: Content of the schema file
            schema_info: Information about the schema structure
            field_changes: List of changes to apply

        Returns:
            Dictionary with update status and content
        """
        updated = False
        updated_content = schema_content
        lines = updated_content.splitlines()

        # Process changes in this order: remove, rename, modify, add

        # Step 1: Process remove operations
        for change in field_changes:
            if change["type"].lower() == "remove":
                field_name = change["field_name"]

                # Check if the field exists in this schema
                if field_name in schema_info["fields"]:
                    field_info = schema_info["fields"][field_name]
                    field_line = field_info["line"]

                    # Remove the field line
                    if 0 <= field_line < len(lines):
                        lines[field_line] = ""
                        updated = True

        # Step 2: Process rename operations
        for change in field_changes:
            if change["type"].lower() == "rename":
                field_name = change["field_name"]
                new_name = change["new_name"]

                # Check if the field exists in this schema
                if field_name in schema_info["fields"]:
                    field_info = schema_info["fields"][field_name]
                    field_line = field_info["line"]

                    # Rename the field
                    if 0 <= field_line < len(lines):
                        lines[field_line] = lines[field_line].replace(
                            field_name, new_name, 1
                        )
                        updated = True

        # Step 3: Process modify operations
        for change in field_changes:
            if change["type"].lower() == "modify":
                field_name = change["field_name"]

                # Check if the field exists in this schema
                if field_name in schema_info["fields"]:
                    field_info = schema_info["fields"][field_name]
                    field_line = field_info["line"]

                    # Prepare the new field definition
                    if 0 <= field_line < len(lines):
                        # Get the current indentation
                        current_line = lines[field_line]
                        indentation = len(current_line) - len(current_line.lstrip())
                        indent_str = " " * indentation

                        # Create the new line
                        new_line = f"{indent_str}{field_name}: {change['definition']}"
                        lines[field_line] = new_line
                        updated = True

        # Step 4: Process add operations
        for change in field_changes:
            if change["type"].lower() == "add":
                field_name = change["field_name"]

                # Check if the field already exists
                if field_name in schema_info["fields"]:
                    continue

                # Find a good insertion point - after the class definition and existing fields
                class_start_pos = schema_info["start_pos"]
                class_line = updated_content[:class_start_pos].count("\n")

                # Find the indentation level
                indentation = 4  # Default indentation
                for line in lines[class_line + 1 :]:
                    if line.strip():
                        indentation = len(line) - len(line.lstrip())
                        break

                # Prepare the new field entry with proper indentation
                indent_str = " " * indentation
                new_field_line = f"{indent_str}{field_name}: {change['definition']}"

                # Insert after class definition or last field
                insertion_line = class_line + 1

                # If there are existing fields, insert after the last one
                if schema_info["fields"]:
                    last_field_line = max(
                        field_info["line"]
                        for field_info in schema_info["fields"].values()
                    )
                    insertion_line = last_field_line + 1

                # Insert the new field
                if 0 <= insertion_line <= len(lines):
                    lines.insert(insertion_line, new_field_line)
                    updated = True

        # Remove empty lines
        lines = [line for line in lines if line != ""]

        # Join the lines back into content
        if updated:
            updated_content = "\n".join(lines)

        return {"updated": updated, "content": updated_content}

    def convert_model_changes_to_schema_changes(
        self, model_changes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Convert SQLAlchemy model changes to Pydantic schema changes

        Args:
            model_changes: List of model field changes

        Returns:
            List of schema field changes with converted definitions
        """
        schema_changes = []

        for change in model_changes:
            new_change = change.copy()

            if "definition" in change:
                # Convert SQLAlchemy column to Pydantic field
                new_change["definition"] = self._convert_sqlalchemy_to_pydantic(
                    change["definition"]
                )

            schema_changes.append(new_change)

        return schema_changes

    def _convert_sqlalchemy_to_pydantic(self, sqlalchemy_definition: str) -> str:
        """Helper method to convert SQLAlchemy column definition to Pydantic field"""
        # Extract the SQLAlchemy type and options
        sa_type_match = re.search(r"Column\(\s*([^,)]+)", sqlalchemy_definition)

        if not sa_type_match:
            # If we can't parse it, return a generic field
            return "str = None"

        sa_type = sa_type_match.group(1).strip()

        # Check for nullable
        nullable = "nullable=False" not in sqlalchemy_definition

        # Default mapping of SQLAlchemy types to Python/Pydantic types
        type_mapping = {
            "String": "str",
            "Text": "str",
            "Integer": "int",
            "BigInteger": "int",
            "SmallInteger": "int",
            "Float": "float",
            "Numeric": "float",
            "Boolean": "bool",
            "Date": "date",
            "DateTime": "datetime",
            "Time": "time",
            "JSON": "Dict",
            "ARRAY": "List",
            "UUID": "UUID",
        }

        # Handle common SQLAlchemy types
        pydantic_type = "Any"  # Default type

        for sa_type_key, py_type in type_mapping.items():
            if sa_type_key in sa_type:
                pydantic_type = py_type
                break

        # Handle Enum types
        if "Enum" in sa_type:
            enum_match = re.search(r"Enum\(\s*([^,)]+)", sa_type)
            if enum_match:
                enum_name = enum_match.group(1).strip()
                pydantic_type = enum_name

        # Create Pydantic field definition
        if nullable:
            return f"{pydantic_type} = None"
        else:
            return f"{pydantic_type}"
