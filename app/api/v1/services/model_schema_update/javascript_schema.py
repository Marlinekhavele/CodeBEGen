import logging
import re
from typing import Any, Dict, List

from app.api.v1.services.model_schema_update.model_schema_base import SchemaUpdater

logger = logging.getLogger(__name__)


class JoiSchemaUpdater(SchemaUpdater):
    """Schema updater for JavaScript Joi validation schemas"""

    def find_schemas(
        self, schema_content: str, entity_name: str
    ) -> List[Dict[str, Any]]:
        """
        Find Joi schemas related to an entity in the content

        Args:
            schema_content: Content of the schema file
            entity_name: Entity name to search for

        Returns:
            List of schema information dictionaries
        """
        schemas = []

        # Entity name variations to search for
        entity_variations = [
            entity_name.lower(),
            entity_name.lower() + "s",
            entity_name.lower() + "schema",
            entity_name.lower() + "validation",
        ]

        # Find Joi schema definitions
        schema_pattern = re.compile(
            r"(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*Joi\.object\(\s*({[\s\S]*?})\s*\)",
            re.MULTILINE,
        )

        for match in schema_pattern.finditer(schema_content):
            schema_name = match.group(1)
            schema_obj = match.group(2)

            # Check if this schema is related to our entity
            if any(variation in schema_name.lower() for variation in entity_variations):
                schema_start = match.start(2)
                schema_end = match.end(2)

                # Find field definitions within the schema
                field_pattern = re.compile(
                    r"([A-Za-z0-9_]+)\s*:\s*Joi\.([\s\S]*?)(?:,|$)", re.MULTILINE
                )
                fields = {}

                for field_match in field_pattern.finditer(schema_obj):
                    field_name = field_match.group(1)
                    field_def = field_match.group(2).strip()

                    fields[field_name] = {
                        "pos": schema_start + field_match.start(),
                        "definition": f"Joi.{field_def}",
                    }

                schemas.append(
                    {
                        "name": schema_name,
                        "start_pos": schema_start,
                        "end_pos": schema_end,
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
        Update a Joi schema with the specified changes

        Args:
            schema_content: Content of the schema file
            schema_info: Information about the schema structure
            field_changes: List of changes to apply

        Returns:
            Dictionary with update status and content
        """
        updated = False
        updated_content = schema_content

        # Process changes in this order: remove, rename, modify, add

        # Step 1: Process remove operations
        for change in field_changes:
            if change["type"].lower() == "remove":
                field_name = change["field_name"]
                if field_name in schema_info["fields"]:
                    field_info = schema_info["fields"][field_name]
                    field_def = field_info["definition"]

                    # Find the full field definition
                    field_pattern = (
                        re.escape(field_name)
                        + r"\s*:\s*"
                        + re.escape(field_def)
                        + r"\s*,?"
                    )
                    field_match = re.search(field_pattern, updated_content)

                    if field_match:
                        # Remove the field
                        updated_content = (
                            updated_content[: field_match.start()]
                            + updated_content[field_match.end() :]
                        )
                        updated = True
                    else:
                        logger.warning(
                            f"Could not locate field {field_name} in the Joi schema"
                        )

        # Step 2: Process rename operations
        for change in field_changes:
            if change["type"].lower() == "rename":
                field_name = change["field_name"]
                new_name = change["new_name"]

                if field_name in schema_info["fields"]:
                    # Find the field
                    field_pattern = r"(" + re.escape(field_name) + r")\s*:"
                    field_match = re.search(field_pattern, updated_content)

                    if field_match:
                        # Rename the field
                        updated_content = (
                            updated_content[: field_match.start(1)]
                            + new_name
                            + updated_content[field_match.end(1) :]
                        )
                        updated = True
                    else:
                        logger.warning(
                            f"Could not locate field {field_name} in the Joi schema"
                        )

        # Step 3: Process modify operations
        for change in field_changes:
            if change["type"].lower() == "modify":
                field_name = change["field_name"]
                if field_name in schema_info["fields"]:
                    field_info = schema_info["fields"][field_name]
                    field_def = field_info["definition"]

                    # Find the field definition
                    field_pattern = (
                        field_name + r"\s*:\s*(" + re.escape(field_def) + r")"
                    )
                    field_match = re.search(field_pattern, updated_content)

                    if field_match:
                        # Replace the field definition
                        updated_content = (
                            updated_content[: field_match.start(1)]
                            + change["definition"]
                            + updated_content[field_match.end(1) :]
                        )
                        updated = True
                    else:
                        logger.warning(
                            f"Could not locate field definition for {field_name} in the Joi schema"
                        )

        # Step 4: Process add operations
        for change in field_changes:
            if change["type"].lower() == "add":
                field_name = change["field_name"]

                # Check if the field already exists
                if field_name in schema_info["fields"]:
                    continue

                # Find a good insertion point - inside the schema object
                schema_start_pos = schema_info["start_pos"]

                # Insert near the beginning of the schema object
                insertion_pos = schema_start_pos + 1

                # Prepare the new field entry
                indent = "  "  # Default indentation
                new_field_entry = (
                    f"\n{indent}{field_name}: {change['definition']},\n{indent}"
                )

                # Insert the new field
                updated_content = (
                    updated_content[:insertion_pos]
                    + new_field_entry
                    + updated_content[insertion_pos:]
                )
                updated = True

        return {"updated": updated, "content": updated_content}

    def convert_model_changes_to_schema_changes(
        self, model_changes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Convert Mongoose/Sequelize model changes to Joi schema changes

        Args:
            model_changes: List of model field changes

        Returns:
            List of schema field changes with converted definitions
        """
        schema_changes = []

        for change in model_changes:
            new_change = change.copy()

            if "definition" in change:
                # Convert model field definition to Joi validation
                new_change["definition"] = self._convert_model_to_joi(
                    change["definition"]
                )

            schema_changes.append(new_change)

        return schema_changes

    def _convert_model_to_joi(self, model_definition: str) -> str:
        """
        Convert a Mongoose/Sequelize field definition to Joi validation

        Args:
            model_definition: Model field definition

        Returns:
            Joi validation definition
        """
        # Extract type information
        type_str = ""
        required = False

        # Check for common type patterns
        if "type: String" in model_definition:
            type_str = "string()"
        elif "type: Number" in model_definition:
            type_str = "number()"
        elif "type: Boolean" in model_definition:
            type_str = "boolean()"
        elif "type: Date" in model_definition:
            type_str = "date()"
        elif "type: Buffer" in model_definition:
            type_str = "binary()"
        elif (
            "type: ObjectId" in model_definition
            or "type: mongoose.Schema.Types.ObjectId" in model_definition
        ):
            type_str = "string().hex().length(24)"
        elif "type: Array" in model_definition or "type: []" in model_definition:
            type_str = "array()"
        elif "type: Object" in model_definition or "type: {}" in model_definition:
            type_str = "object()"
        elif "DataTypes.STRING" in model_definition:
            type_str = "string()"
        elif (
            "DataTypes.INTEGER" in model_definition
            or "DataTypes.BIGINT" in model_definition
        ):
            type_str = "number().integer()"
        elif (
            "DataTypes.FLOAT" in model_definition
            or "DataTypes.DOUBLE" in model_definition
            or "DataTypes.DECIMAL" in model_definition
        ):
            type_str = "number()"
        elif "DataTypes.BOOLEAN" in model_definition:
            type_str = "boolean()"
        elif "DataTypes.DATE" in model_definition:
            type_str = "date()"
        elif "DataTypes.JSON" in model_definition:
            type_str = "object()"
        elif "DataTypes.ARRAY" in model_definition:
            type_str = "array()"
        elif "DataTypes.UUID" in model_definition:
            type_str = "string().guid()"
        else:
            # Default to string if we can't determine the type
            type_str = "string()"

        # Check if the field is required
        if (
            "required: true" in model_definition.lower()
            or "allowNull: false" in model_definition.lower()
        ):
            required = True

        # Build the Joi validator
        joi_def = f"Joi.{type_str}"

        if required:
            joi_def += ".required()"
        else:
            joi_def += ".optional()"

        # Handle enum values
        enum_match = re.search(r"enum\s*:\s*\[(.*?)\]", model_definition)
        if enum_match:
            # Extract enum values
            enum_values = enum_match.group(1).strip()
            if enum_values:
                # Split on commas and clean up the values
                values = [v.strip() for v in enum_values.split(",")]
                values_str = ", ".join(values)
                joi_def += f".valid({values_str})"

        # Handle default values
        default_match = re.search(r"default\s*:\s*([^,}]+)", model_definition)
        if default_match:
            default_value = default_match.group(1).strip()
            if default_value:
                # Don't use .default() for Joi since it applies the default in validation
                # Just note it in a comment
                joi_def += f" /* default: {default_value} */"

        return joi_def


class ExpressValidatorSchemaUpdater(SchemaUpdater):
    """Schema updater for Express-validator schemas"""

    def find_schemas(
        self, schema_content: str, entity_name: str
    ) -> List[Dict[str, Any]]:
        """
        Find Express-validator schemas related to an entity in the content

        Args:
            schema_content: Content of the schema file
            entity_name: Entity name to search for

        Returns:
            List of schema information dictionaries
        """
        schemas = []

        # Entity name variations to search for
        entity_variations = [
            entity_name.lower(),
            entity_name.lower() + "s",
            entity_name.lower() + "validation",
            entity_name.lower() + "validator",
        ]

        # Find Express-validator schema arrays
        schema_pattern = re.compile(
            r"(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*\[([\s\S]*?)\]", re.MULTILINE
        )

        for match in schema_pattern.finditer(schema_content):
            schema_name = match.group(1)
            schema_array = match.group(2)

            # Check if this schema is related to our entity
            if any(variation in schema_name.lower() for variation in entity_variations):
                schema_start = match.start(2)
                schema_end = match.end(2)

                # Express-validator uses function calls like check('fieldName').isString()
                # We need to extract the field names from these calls
                field_pattern = re.compile(
                    r'(?:check|body|param|query)\([\'"]([A-Za-z0-9_]+)[\'"]\)([\s\S]*?)(?:,|\n|$)',
                    re.MULTILINE,
                )
                fields = {}

                for field_match in field_pattern.finditer(schema_array):
                    field_name = field_match.group(1)
                    field_def = field_match.group(2).strip()

                    fields[field_name] = {
                        "pos": schema_start + field_match.start(),
                        "definition": f"check('{field_name}'){field_def}",
                    }

                schemas.append(
                    {
                        "name": schema_name,
                        "start_pos": schema_start,
                        "end_pos": schema_end,
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
        Update an Express-validator schema with the specified changes

        Args:
            schema_content: Content of the schema file
            schema_info: Information about the schema structure
            field_changes: List of changes to apply

        Returns:
            Dictionary with update status and content
        """
        updated = False
        updated_content = schema_content

        # Process changes in this order: remove, rename, modify, add

        # Step 1: Process remove operations
        for change in field_changes:
            if change["type"].lower() == "remove":
                field_name = change["field_name"]
                if field_name in schema_info["fields"]:
                    field_info = schema_info["fields"][field_name]
                    field_def = field_info["definition"]

                    # Find the full field validation
                    field_pattern = re.escape(field_def) + r"\s*,?"
                    field_match = re.search(field_pattern, updated_content)

                    if field_match:
                        # Remove the field validation
                        updated_content = (
                            updated_content[: field_match.start()]
                            + updated_content[field_match.end() :]
                        )
                        updated = True
                    else:
                        logger.warning(
                            f"Could not locate field {field_name} in the Express-validator schema"
                        )

        # Step 2: Process rename operations
        for change in field_changes:
            if change["type"].lower() == "rename":
                field_name = change["field_name"]
                new_name = change["new_name"]

                if field_name in schema_info["fields"]:
                    # Find all instances of the field name in quotes
                    field_pattern = r'([\'"])' + re.escape(field_name) + r'([\'"])'

                    # Replace all occurrences
                    updated_content_new = re.sub(
                        field_pattern, r"\1" + new_name + r"\2", updated_content
                    )

                    if updated_content_new != updated_content:
                        updated_content = updated_content_new
                        updated = True
                    else:
                        logger.warning(
                            f"Could not locate field {field_name} in the Express-validator schema"
                        )

        # Step 3: Process modify operations
        for change in field_changes:
            if change["type"].lower() == "modify":
                field_name = change["field_name"]
                if field_name in schema_info["fields"]:
                    field_info = schema_info["fields"][field_name]
                    field_def = field_info["definition"]

                    # For express-validator, we might need to replace the entire validation chain
                    field_pattern = re.escape(field_def) + r",?"
                    field_match = re.search(field_pattern, updated_content)

                    if field_match:
                        # Replace the field validation
                        new_def = change["definition"]
                        if not new_def.endswith(",") and field_match.group(0).endswith(
                            ","
                        ):
                            new_def += ","

                        updated_content = (
                            updated_content[: field_match.start()]
                            + new_def
                            + updated_content[field_match.end() :]
                        )
                        updated = True
                    else:
                        logger.warning(
                            f"Could not locate field definition for {field_name} in the Express-validator schema"
                        )

        # Step 4: Process add operations
        for change in field_changes:
            if change["type"].lower() == "add":
                field_name = change["field_name"]

                # Check if the field already exists
                if field_name in schema_info["fields"]:
                    continue

                # Find a good insertion point - at the end of the schema array
                schema_end_pos = schema_info["end_pos"]

                # Prepare the new field validation
                new_def = change["definition"]
                if not new_def.endswith(","):
                    new_def += ","

                # Insert the new field validation
                updated_content = (
                    updated_content[:schema_end_pos]
                    + new_def
                    + "\n  "
                    + updated_content[schema_end_pos:]
                )
                updated = True

        return {"updated": updated, "content": updated_content}

    def convert_model_changes_to_schema_changes(
        self, model_changes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Convert model changes to Express-validator schema changes

        Args:
            model_changes: List of model field changes

        Returns:
            List of schema field changes with converted definitions
        """
        schema_changes = []

        for change in model_changes:
            new_change = change.copy()

            if "definition" in change:
                # Convert model field definition to Express-validator
                new_change["definition"] = self._convert_model_to_express_validator(
                    change["field_name"], change["definition"]
                )

            schema_changes.append(new_change)

        return schema_changes

    def _convert_model_to_express_validator(
        self, field_name: str, model_definition: str
    ) -> str:
        """
        Convert a model field definition to Express-validator validation

        Args:
            field_name: Name of the field
            model_definition: Model field definition

        Returns:
            Express-validator validation definition
        """
        # Start with the check call
        validator = f"check('{field_name}')"

        # Add existence check if required
        if (
            "required: true" in model_definition.lower()
            or "allowNull: false" in model_definition.lower()
        ):
            validator += ".notEmpty().withMessage('Field is required')"
        else:
            validator += ".optional()"

        # Add type validation based on the field type
        if "type: String" in model_definition or "DataTypes.STRING" in model_definition:
            validator += ".isString().withMessage('Must be a string')"
        elif (
            "type: Number" in model_definition
            or "DataTypes.INTEGER" in model_definition
            or "DataTypes.FLOAT" in model_definition
        ):
            validator += ".isNumeric().withMessage('Must be a number')"
        elif (
            "type: Boolean" in model_definition
            or "DataTypes.BOOLEAN" in model_definition
        ):
            validator += ".isBoolean().withMessage('Must be a boolean')"
        elif "type: Date" in model_definition or "DataTypes.DATE" in model_definition:
            validator += ".isISO8601().withMessage('Must be a valid date')"
        elif "type: Buffer" in model_definition:
            # Not a standard validation, but we can check if it's base64
            validator += ".isBase64().withMessage('Must be base64 encoded')"
        elif (
            "type: ObjectId" in model_definition
            or "type: mongoose.Schema.Types.ObjectId" in model_definition
        ):
            validator += ".isMongoId().withMessage('Must be a valid ID')"
        elif (
            "type: Array" in model_definition
            or "type: []" in model_definition
            or "DataTypes.ARRAY" in model_definition
        ):
            validator += ".isArray().withMessage('Must be an array')"
        elif (
            "type: Object" in model_definition
            or "type: {}" in model_definition
            or "DataTypes.JSON" in model_definition
        ):
            # Custom validation for an object
            validator += ".custom(value => typeof value === 'object').withMessage('Must be an object')"
        elif "DataTypes.UUID" in model_definition:
            validator += ".isUUID().withMessage('Must be a valid UUID')"

        # Handle enum values
        enum_match = re.search(r"enum\s*:\s*\[(.*?)\]", model_definition)
        if enum_match:
            enum_values = enum_match.group(1).strip()
            if enum_values:
                values = [v.strip() for v in enum_values.split(",")]
                values_str = ", ".join(values)
                validator += f".isIn([{values_str}]).withMessage('Must be one of: {', '.join(values)}')"

        return validator


class GenericJSSchemaUpdater(SchemaUpdater):
    """Generic schema updater for JavaScript validation schemas"""

    def find_schemas(
        self, schema_content: str, entity_name: str
    ) -> List[Dict[str, Any]]:
        """
        Find JS validation schemas related to an entity in the content

        Args:
            schema_content: Content of the schema file
            entity_name: Entity name to search for

        Returns:
            List of schema information dictionaries
        """
        schemas = []

        # Try to find Joi schemas first
        joi_updater = JoiSchemaUpdater()
        joi_schemas = joi_updater.find_schemas(schema_content, entity_name)
        if joi_schemas:
            return joi_schemas

        # Try to find Express-validator schemas next
        express_updater = ExpressValidatorSchemaUpdater()
        express_schemas = express_updater.find_schemas(schema_content, entity_name)
        if express_schemas:
            return express_schemas

        # If we can't find specific schema types, look for generic object definitions
        entity_variations = [
            entity_name.lower(),
            entity_name.lower() + "s",
            entity_name.lower() + "schema",
            entity_name.lower() + "validation",
        ]

        # Look for object definitions
        schema_pattern = re.compile(
            r"(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*({[\s\S]*?});", re.MULTILINE
        )

        for match in schema_pattern.finditer(schema_content):
            schema_name = match.group(1)
            schema_obj = match.group(2)

            # Check if this schema is related to our entity
            if any(variation in schema_name.lower() for variation in entity_variations):
                schema_start = match.start(2)
                schema_end = match.end(2)

                # Find field definitions within the object
                field_pattern = re.compile(
                    r"([A-Za-z0-9_]+)\s*:\s*([^,}]+)(?:,|$)", re.MULTILINE
                )
                fields = {}

                for field_match in field_pattern.finditer(schema_obj):
                    field_name = field_match.group(1)
                    field_def = field_match.group(2).strip()

                    fields[field_name] = {
                        "pos": schema_start + field_match.start(),
                        "definition": field_def,
                    }

                schemas.append(
                    {
                        "name": schema_name,
                        "start_pos": schema_start,
                        "end_pos": schema_end,
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
        Update a generic JS schema with the specified changes

        Args:
            schema_content: Content of the schema file
            schema_info: Information about the schema structure
            field_changes: List of changes to apply

        Returns:
            Dictionary with update status and content
        """
        # Check for keywords to determine schema type
        if "Joi." in schema_content:
            updater = JoiSchemaUpdater()
            return updater.update_schema(schema_content, schema_info, field_changes)
        elif "check(" in schema_content or "body(" in schema_content:
            updater = ExpressValidatorSchemaUpdater()
            return updater.update_schema(schema_content, schema_info, field_changes)

        # Generic object update (fallback)
        updated = False
        updated_content = schema_content

        # Process changes in this order: remove, rename, modify, add

        # Step 1: Process remove operations
        for change in field_changes:
            if change["type"].lower() == "remove":
                field_name = change["field_name"]
                if field_name in schema_info["fields"]:
                    field_info = schema_info["fields"][field_name]
                    field_def = field_info["definition"]

                    # Find the full field entry
                    field_pattern = (
                        re.escape(field_name)
                        + r"\s*:\s*"
                        + re.escape(field_def)
                        + r"\s*,?"
                    )
                    field_match = re.search(field_pattern, updated_content)

                    if field_match:
                        # Remove the field entry
                        updated_content = (
                            updated_content[: field_match.start()]
                            + updated_content[field_match.end() :]
                        )
                        updated = True
                    else:
                        logger.warning(
                            f"Could not locate field {field_name} in the JavaScript schema"
                        )

        # Step 2: Process rename operations
        for change in field_changes:
            if change["type"].lower() == "rename":
                field_name = change["field_name"]
                new_name = change["new_name"]

                if field_name in schema_info["fields"]:
                    # Find the field name
                    field_pattern = r"(" + re.escape(field_name) + r")\s*:"
                    field_match = re.search(field_pattern, updated_content)

                    if field_match:
                        # Rename the field
                        updated_content = (
                            updated_content[: field_match.start(1)]
                            + new_name
                            + updated_content[field_match.end(1) :]
                        )
                        updated = True
                    else:
                        logger.warning(
                            f"Could not locate field {field_name} in the JavaScript schema"
                        )

        # Step 3: Process modify operations
        for change in field_changes:
            if change["type"].lower() == "modify":
                field_name = change["field_name"]
                if field_name in schema_info["fields"]:
                    field_info = schema_info["fields"][field_name]
                    field_def = field_info["definition"]

                    # Find the field definition
                    field_pattern = (
                        field_name + r"\s*:\s*(" + re.escape(field_def) + r")"
                    )
                    field_match = re.search(field_pattern, updated_content)

                    if field_match:
                        # Replace the field definition
                        updated_content = (
                            updated_content[: field_match.start(1)]
                            + change["definition"]
                            + updated_content[field_match.end(1) :]
                        )
                        updated = True
                    else:
                        logger.warning(
                            f"Could not locate field definition for {field_name} in the JavaScript schema"
                        )

        # Step 4: Process add operations
        for change in field_changes:
            if change["type"].lower() == "add":
                field_name = change["field_name"]

                # Check if the field already exists
                if field_name in schema_info["fields"]:
                    continue

                # Find the insertion point - inside the schema object
                schema_start_pos = schema_info["start_pos"]

                # Insert at the beginning of the object
                insertion_pos = schema_start_pos + 1

                # Prepare the new field entry
                indent = "  "  # Default indentation
                new_field_entry = (
                    f"\n{indent}{field_name}: {change['definition']},\n{indent}"
                )

                # Insert the new field
                updated_content = (
                    updated_content[:insertion_pos]
                    + new_field_entry
                    + updated_content[insertion_pos:]
                )
                updated = True

        return {"updated": updated, "content": updated_content}

    def convert_model_changes_to_schema_changes(
        self, model_changes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Convert model changes to generic JS schema changes

        Args:
            model_changes: List of model field changes

        Returns:
            List of schema field changes with converted definitions
        """
        # Try to use more specific converters if possible based on context
        joi_updater = JoiSchemaUpdater()
        return joi_updater.convert_model_changes_to_schema_changes(model_changes)
