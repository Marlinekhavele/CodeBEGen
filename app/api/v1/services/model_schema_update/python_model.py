import ast
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.api.v1.services.model_schema_update.model_schema_base import ModelUpdater

logger = logging.getLogger(__name__)

#
# CONCRETE MODEL UPDATER IMPLEMENTATIONS
#


class PythonModelUpdater(ModelUpdater):
    """Model updater for Python SQLAlchemy models"""

    def parse_model_structure(
        self, model_code: str, entity_name: str
    ) -> Dict[str, Any]:
        """
        Parse the structure of a SQLAlchemy model file

        Args:
            model_code: The source code of the model file
            entity_name: The name of the entity being modified

        Returns:
            Dictionary containing the model structure
        """
        structure = {
            "class_definition": {
                "start_line": -1,
                "end_line": -1,
                "name": "",
                "bases": [],
            },
            "fields": {},
            "imports": [],
            "enums": {},
        }

        # Try to parse the code into an AST
        try:
            tree = ast.parse(model_code)

            # Find all import statements
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        structure["imports"].append(
                            {"line": node.lineno, "import": f"import {name.name}"}
                        )
                elif isinstance(node, ast.ImportFrom):
                    names = ", ".join(name.name for name in node.names)
                    structure["imports"].append(
                        {
                            "line": node.lineno,
                            "import": f"from {node.module} import {names}",
                        }
                    )

            # Find class definitions
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if this is the target entity class
                    class_name = node.name.lower()
                    entity_variations = [
                        entity_name.lower(),
                        entity_name.lower() + "s",
                        entity_name.lower().rstrip("s"),
                    ]

                    if class_name in entity_variations:
                        # Found our target class
                        structure["class_definition"]["start_line"] = node.lineno
                        structure["class_definition"]["name"] = node.name
                        structure["class_definition"]["bases"] = [
                            base.id for base in node.bases if isinstance(base, ast.Name)
                        ]

                        # Get the last line of the class
                        max_line = node.lineno
                        for child_node in ast.walk(node):
                            if hasattr(child_node, "lineno"):
                                max_line = max(max_line, child_node.lineno)
                        structure["class_definition"]["end_line"] = max_line

                        # Find field definitions
                        for child in node.body:
                            if isinstance(child, ast.Assign):
                                for target in child.targets:
                                    if isinstance(target, ast.Name):
                                        # Check if this is a SQLAlchemy Column
                                        if isinstance(child.value, ast.Call):
                                            if (
                                                isinstance(child.value.func, ast.Name)
                                                and child.value.func.id == "Column"
                                            ):
                                                field_name = target.id
                                                # Extract the column definition
                                                col_def_start = child.value.col_offset
                                                col_def_end = (
                                                    child.end_col_offset
                                                    if hasattr(child, "end_col_offset")
                                                    else -1
                                                )

                                                lines = model_code.splitlines()
                                                if 0 <= child.lineno - 1 < len(lines):
                                                    line = lines[child.lineno - 1]
                                                    if col_def_start < len(line):
                                                        if (
                                                            col_def_end > 0
                                                            and col_def_end <= len(line)
                                                        ):
                                                            definition = line[
                                                                col_def_start:col_def_end
                                                            ]
                                                        else:
                                                            definition = line[
                                                                col_def_start:
                                                            ]
                                                        structure["fields"][
                                                            field_name
                                                        ] = {
                                                            "line": child.lineno,
                                                            "definition": definition.strip(),
                                                        }

                    # Find Enum definitions in the same file
                    for enum_node in ast.walk(tree):
                        if isinstance(enum_node, ast.ClassDef):
                            for base in enum_node.bases:
                                if isinstance(base, ast.Name) and base.id == "Enum":
                                    enum_name = enum_node.name
                                    enum_values = []

                                    for enum_item in enum_node.body:
                                        if isinstance(enum_item, ast.Assign):
                                            for target in enum_item.targets:
                                                if isinstance(target, ast.Name):
                                                    enum_values.append(target.id)

                                    structure["enums"][enum_name] = {
                                        "line": enum_node.lineno,
                                        "values": enum_values,
                                    }

        except SyntaxError as e:
            logger.error(f"Failed to parse Python model code: {e}")
            # Fall back to regex-based parsing
            structure = self._parse_with_regex(model_code, entity_name)

        return structure

    def _parse_with_regex(self, model_code: str, entity_name: str) -> Dict[str, Any]:
        """Fallback parsing method using regex"""
        structure = {
            "class_definition": {
                "start_line": -1,
                "end_line": -1,
                "name": "",
                "bases": [],
            },
            "fields": {},
            "imports": [],
            "enums": {},
        }

        lines = model_code.splitlines()

        # Find the class definition
        for i, line in enumerate(lines):
            class_match = re.match(r"\s*class\s+([A-Za-z0-9_]+)(?:\(([^)]+)\))?:", line)
            if class_match:
                class_name = class_match.group(1)
                entity_variations = [
                    entity_name.lower(),
                    entity_name.lower() + "s",
                    entity_name.lower().rstrip("s"),
                ]

                if class_name.lower() in entity_variations:
                    structure["class_definition"]["start_line"] = i + 1
                    structure["class_definition"]["name"] = class_name
                    if class_match.group(2):
                        structure["class_definition"]["bases"] = [
                            base.strip() for base in class_match.group(2).split(",")
                        ]

                    # Find the end of the class by indentation
                    class_indent = len(line) - len(line.lstrip())
                    for j in range(i + 1, len(lines)):
                        # If we find a line with same or less indentation, it's outside the class
                        if (
                            lines[j].strip()
                            and len(lines[j]) - len(lines[j].lstrip()) <= class_indent
                        ):
                            structure["class_definition"]["end_line"] = j
                            break
                    else:
                        # If we reach the end of the file
                        structure["class_definition"]["end_line"] = len(lines)

                    # Find field definitions within the class
                    for j in range(i + 1, structure["class_definition"]["end_line"]):
                        field_match = re.match(
                            r"\s+([A-Za-z0-9_]+)\s*=\s*(Column\(.+)", lines[j]
                        )
                        if field_match:
                            field_name = field_match.group(1)
                            definition = field_match.group(2).strip()
                            structure["fields"][field_name] = {
                                "line": j + 1,
                                "definition": definition,
                            }

        # Find imports
        for i, line in enumerate(lines):
            import_match = re.match(r"\s*(?:from\s+.+\s+import|import)\s+.+", line)
            if import_match:
                structure["imports"].append({"line": i + 1, "import": line.strip()})

        # Find Enum definitions
        for i, line in enumerate(lines):
            enum_match = re.match(
                r"\s*class\s+([A-Za-z0-9_]+)\s*\(\s*Enum\s*\)\s*:", line
            )
            if enum_match:
                enum_name = enum_match.group(1)
                enum_values = []

                # Find the end of the enum by indentation
                enum_indent = len(line) - len(line.lstrip())
                enum_end = len(lines)
                for j in range(i + 1, len(lines)):
                    # If we find a line with same or less indentation, it's outside the enum
                    if (
                        lines[j].strip()
                        and len(lines[j]) - len(lines[j].lstrip()) <= enum_indent
                    ):
                        enum_end = j
                        break

                # Extract enum values
                for j in range(i + 1, enum_end):
                    value_match = re.match(r"\s+([A-Za-z0-9_]+)\s*=", lines[j])
                    if value_match:
                        enum_values.append(value_match.group(1))

                structure["enums"][enum_name] = {"line": i + 1, "values": enum_values}

        return structure

    def update_model(
        self,
        model_path: Path,
        entity_name: str,
        field_changes: List[Dict[str, Any]],
        existing_model_code: str,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Update a SQLAlchemy model with the specified changes
        Ensures all required SQLAlchemy types are imported (e.g., Boolean, DateTime, etc.).

        Args:
            model_path: Path to the model file
            entity_name: Name of the entity being modified
            field_changes: List of changes to apply
            existing_model_code: Current content of the model file

        Returns:
            Tuple containing updated model code and change summary
        """
        # Parse the model structure
        structure = self.parse_model_structure(existing_model_code, entity_name)

        # Initialize tracking for changes
        added_fields = []
        modified_fields = []
        removed_fields = []
        renamed_fields = []

        # If we couldn't find the target class, we can't make changes
        if structure["class_definition"]["start_line"] < 0:
            logger.error(f"Could not find class definition for {entity_name}")
            return existing_model_code, {
                "changes_made": False,
                "error": f"Could not find class definition for {entity_name}",
            }

        lines = existing_model_code.splitlines()

        # Process changes in this order: remove, rename, modify, add
        # This avoids conflicts when making multiple types of changes

        # Step 1: Process remove operations
        for change in field_changes:
            if change["type"].lower() == "remove":
                field_name = change["field_name"]
                if field_name in structure["fields"]:
                    # Remove the field from the class
                    field_line = structure["fields"][field_name]["line"] - 1
                    lines[field_line] = ""  # Mark line for removal
                    removed_fields.append(field_name)
                else:
                    logger.warning(
                        f"Cannot remove field {field_name}: not found in model"
                    )

        # Step 2: Process rename operations
        for change in field_changes:
            if change["type"].lower() == "rename":
                field_name = change["field_name"]
                new_name = change["new_name"]

                if field_name in structure["fields"]:
                    # Rename the field
                    field_line = structure["fields"][field_name]["line"] - 1
                    lines[field_line] = lines[field_line].replace(
                        field_name, new_name, 1
                    )
                    renamed_fields.append({"old": field_name, "new": new_name})

                    # Update the structure to reflect the rename
                    structure["fields"][new_name] = structure["fields"][field_name]
                    del structure["fields"][field_name]
                else:
                    logger.warning(
                        f"Cannot rename field {field_name}: not found in model"
                    )

        # Step 3: Process modify operations
        for change in field_changes:
            if change["type"].lower() == "modify":
                field_name = change["field_name"]
                if field_name in structure["fields"]:
                    # Extract the current indentation
                    field_line = structure["fields"][field_name]["line"] - 1
                    current_line = lines[field_line]
                    indentation = len(current_line) - len(current_line.lstrip())
                    indent_str = " " * indentation

                    # Create the new line with the modified definition
                    new_line = f"{indent_str}{field_name} = {change['definition']}"
                    lines[field_line] = new_line
                    modified_fields.append(field_name)
                else:
                    logger.warning(
                        f"Cannot modify field {field_name}: not found in model"
                    )

        # Step 4: Process add operations
        for change in field_changes:
            if change["type"].lower() == "add":
                field_name = change["field_name"]

                # Check if the field already exists
                if field_name in structure["fields"]:
                    logger.warning(f"Field {field_name} already exists in model")
                    continue

                # Find the insertion point - we'll insert before the end of the class
                # but after the last field if one exists
                insertion_line = structure["class_definition"]["end_line"] - 1

                # If there are existing fields, insert after the last one
                if structure["fields"]:
                    last_field_line = max(
                        info["line"] for info in structure["fields"].values()
                    )
                    insertion_line = last_field_line

                # Determine the indentation from either the class definition or existing fields
                indentation = 4  # Default indentation
                if structure["fields"]:
                    # Use the indentation of the last field
                    last_field_line = (
                        max(info["line"] for info in structure["fields"].values()) - 1
                    )
                    indentation = len(lines[last_field_line]) - len(
                        lines[last_field_line].lstrip()
                    )
                else:
                    # Use the indentation of the class definition plus 4
                    class_line = structure["class_definition"]["start_line"] - 1
                    if 0 <= class_line < len(lines):
                        indentation = (
                            len(lines[class_line]) - len(lines[class_line].lstrip()) + 4
                        )

                # Create the new field line
                indent_str = " " * indentation
                new_field_line = f"{indent_str}{field_name} = {change['definition']}"

                # Insert the new field after the insertion line
                lines.insert(insertion_line, new_field_line)

                # Update line numbers in the structure
                for f_name, f_info in structure["fields"].items():
                    if f_info["line"] > insertion_line + 1:
                        f_info["line"] += 1

                # Update the class end line
                structure["class_definition"]["end_line"] += 1

                # Add the new field to the structure
                structure["fields"][field_name] = {
                    "line": insertion_line + 1,
                    "definition": change["definition"],
                }

                added_fields.append(field_name)

        # Remove empty lines (from remove operations)
        lines = [line for line in lines if line != ""]

        # Join the lines back into a single string
        updated_code = "\n".join(lines)

        # Detect all used SQLAlchemy types in the model (including new fields)
        used_types = set()
        matches = re.findall(r"Column\(([^)]*)\)", updated_code)
        for match in matches:
            for type_candidate in [
                "String",
                "Integer",
                "DateTime",
                "Boolean",
                "Float",
                "ForeignKey",
                "UUID",
            ]:
                if type_candidate in match:
                    used_types.add(type_candidate)
        # Parse existing imports
        lines = updated_code.splitlines()
        import_lines = [
            i
            for i, l in enumerate(lines)
            if l.strip().startswith("from sqlalchemy import")
        ]
        if import_lines:
            import_idx = import_lines[0]
            import_line = lines[import_idx]
            # Add missing types to the import line
            for t in used_types:
                if t not in import_line:
                    import_line = import_line.rstrip() + f", {t}"
            lines[import_idx] = import_line
            updated_content = "\n".join(lines)
        else:
            # If no import line, add one at the top after any docstring or comments
            insert_idx = 0
            for i, l in enumerate(lines):
                if not l.strip().startswith("#") and l.strip():
                    insert_idx = i
                    break
            import_line = "from sqlalchemy import Column, String, Integer, DateTime, Boolean, Float, ForeignKey, UUID"
            lines.insert(insert_idx, import_line)
            updated_content = "\n".join(lines)

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

        # Before writing the updated model, ensure referenced models exist
        models_dir = model_path.parent
        self.ensure_referenced_models_exist(existing_model_code, models_dir)

        return updated_content, change_summary

    @staticmethod
    def ensure_referenced_models_exist(model_code: str, models_dir: Path):
        """
        Scan model_code for ForeignKey references and ensure referenced models exist.
        If not, generate a minimal model for the referenced table.
        """
        import re

        foreign_keys = re.findall(r"ForeignKey\([\'\"](\w+)\.id[\'\"]", model_code)
        for table in set(foreign_keys):
            model_file = models_dir / f"{table}.py"
            if not model_file.exists():
                # Generate a minimal model for the referenced table
                minimal_model = f"""from sqlalchemy import Column, String\nfrom core.database import Base\n\nclass {table.capitalize()}(Base):\n    __tablename__ = \"{table}s\"\n    id = Column(String, primary_key=True)\n"""
                model_file.write_text(minimal_model)
                print(f"Generated missing referenced model: {table}")
