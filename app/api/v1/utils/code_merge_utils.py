import os
import re
from typing import List

from app.api.v1.services.langchain_service import LangchainService


def extract_js_function_names(code: str) -> List[str]:
    """
    Extracts function names from a JavaScript file (supports function declarations and exports).
    """
    # Match: function foo(...) or const foo = (...) => or exports.foo = ...
    patterns = [
        r"function\s+([a-zA-Z0-9_]+)\s*\(",
        r"const\s+([a-zA-Z0-9_]+)\s*=\s*\(.*?=>",
        r"exports\.([a-zA-Z0-9_]+)\s*=",
        r"module\.exports\s*=\s*\{([^}]+)\}",
    ]
    names = set()
    for pattern in patterns:
        for match in re.findall(pattern, code):
            if isinstance(match, tuple):
                match = match[0]
            if "," in match:
                # For module.exports = { foo, bar }
                for n in match.split(","):
                    names.add(n.strip())
            else:
                names.add(match.strip())
    return list(names)


def extract_py_function_names(code: str) -> List[str]:
    """
    Extracts function names from a Python file (def ...):
    """
    return re.findall(r"^def\s+([a-zA-Z0-9_]+)\s*\(", code, re.MULTILINE)


def extract_py_class_names(code: str) -> List[str]:
    """
    Extracts class names from a Python file.
    """
    return re.findall(r"^class\s+([a-zA-Z0-9_]+)\s*[\(:]", code, re.MULTILINE)


def extract_py_model_fields(code: str) -> List[str]:
    """
    Extracts field names from a SQLAlchemy model class.
    """
    return re.findall(r"^\s+([a-zA-Z0-9_]+)\s*=\s*Column\(", code, re.MULTILINE)


def extract_required_py_helpers_from_endpoint(code: str) -> List[str]:
    """
    Extracts required helper function names from a Python endpoint file.
    Looks for import statements like:
    from helpers.book_helpers import get_all_books, get_book_by_id
    and function calls in the code body.
    """
    import_names = set()
    # Find imports from helpers
    import_pattern = re.compile(
        r"from\s+helpers\.[a-zA-Z0-9_]+_helpers\s+import\s+([a-zA-Z0-9_,\s]+)"
    )
    for match in import_pattern.findall(code):
        for name in match.split(","):
            import_names.add(name.strip())
    # Optionally, also look for direct calls (e.g., get_all_books(...))
    call_pattern = re.compile(r"([a-zA-Z0-9_]+)\s*\(")
    for match in call_pattern.findall(code):
        if match not in import_names and not match.startswith("test_"):
            import_names.add(match)
    return list(import_names)


async def merge_and_append_missing_py_helpers(
    helpers_file_path: str,
    endpoint_code: str,
    model_code: str,
    schema_code: str,
    entity_name: str,
    entity_description: str,
    project_id: str = None,
    language: str = "python",
) -> bool:
    """
    Ensures all required helper functions are present in the helpers file.
    Only generates and appends missing helpers.
    Returns True if any new helpers were added, False otherwise.
    """
    # Read existing helpers file (if exists)
    if os.path.exists(helpers_file_path):
        with open(helpers_file_path, "r", encoding="utf-8") as f:
            existing_code = f.read()
    else:
        existing_code = ""

    from .code_merge_utils import (
        extract_py_function_names,
        extract_required_py_helpers_from_endpoint,
    )

    implemented = set(extract_py_function_names(existing_code))
    required = set(extract_required_py_helpers_from_endpoint(endpoint_code))
    missing = required - implemented
    if not missing:
        return False  # Nothing to do

    # Generate only the missing helpers using the LLM/template
    # (You may want to pass only the missing names to the template, or filter after generation)
    generated = LangchainService.generate_helpers_sync(
        project_id=project_id,
        entity_name=entity_name,
        entity_description=entity_description,
        endpoint_code=endpoint_code,
        model_code=model_code,
        schema_code=schema_code,
        only_functions=list(missing),
        language="python" if language.lower() in ["py", "python"] else "javascript",
    )
    new_helpers_code = generated.get("generated_code", "")
    # Optionally, filter new_helpers_code to include only the missing functions
    # (if your template generates more than requested)
    # Append to the helpers file
    with open(helpers_file_path, "a", encoding="utf-8") as f:
        f.write("\n\n" + new_helpers_code)
    return True


def extract_required_js_helpers_from_endpoint(code: str) -> List[str]:
    """
    Extracts required helper function names from a JavaScript endpoint file.
    Looks for imports like:
    const { getAllBooks, getBookById } = require('../utils/book.utils');
    and function calls in the code body.
    """
    import_names = set()
    # Find destructured imports from utils
    import_pattern = re.compile(
        r"const\s+\{([^}]+)\}\s*=\s*require\(['\"]\.\./utils/[a-zA-Z0-9_]+\.utils['\"]\)"
    )
    for match in import_pattern.findall(code):
        for name in match.split(","):
            import_names.add(name.strip())
    # Optionally, also look for direct calls (e.g., getAllBooks(...))
    call_pattern = re.compile(r"([a-zA-Z0-9_]+)\s*\(")
    for match in call_pattern.findall(code):
        if match not in import_names and not match.startswith("test_"):
            import_names.add(match)
    return list(import_names)


async def merge_and_append_missing_js_helpers(
    helpers_file_path: str,
    endpoint_code: str,
    model_code: str,
    schema_code: str,
    entity_name: str,
    entity_description: str,
    project_id: str = None,
) -> bool:
    """
    Ensures all required helper functions are present in the JS helpers file.
    Only generates and appends missing helpers.
    Returns True if any new helpers were added, False otherwise.
    """
    # Read existing helpers file (if exists)
    if os.path.exists(helpers_file_path):
        with open(helpers_file_path, "r", encoding="utf-8") as f:
            existing_code = f.read()
    else:
        existing_code = ""

    implemented = set(extract_js_function_names(existing_code))
    required = set(extract_required_js_helpers_from_endpoint(endpoint_code))
    missing = required - implemented
    if not missing:
        return False  # Nothing to do

    # Generate only the missing helpers using the LLM/template
    # (You may want to pass only the missing names to the template, or filter after generation)
    generated = LangchainService.generate_helpers_sync(
        project_id=project_id,
        entity_name=entity_name,
        entity_description=entity_description,
        endpoint_code=endpoint_code,
        model_code=model_code,
        schema_code=schema_code,
        only_functions=list(missing),
        language="javascript",
    )
    new_helpers_code = generated.get("generated_code", "")
    # Append to the helpers file
    with open(helpers_file_path, "a", encoding="utf-8") as f:
        f.write("\n\n" + new_helpers_code)
    return True


def merge_and_append_missing_py_model_fields(
    model_file_path: str,
    required_fields: List[str],
    entity_name: str,
    entity_description: str,
    project_id: str = None,
) -> bool:
    """
    Ensures all required model fields are present in the model file.
    Only generates and appends missing fields.
    Returns True if any new fields were added, False otherwise.
    """
    if os.path.exists(model_file_path):
        with open(model_file_path, "r", encoding="utf-8") as f:
            existing_code = f.read()
    else:
        existing_code = ""

    implemented = set(extract_py_model_fields(existing_code))
    missing = set(required_fields) - implemented
    if not missing:
        return False

    # Generate only the missing fields using the LLM/template
    generated = LangchainService.generate_model_fields_sync(
        project_id=project_id,
        entity_name=entity_name,
        entity_description=entity_description,
        only_fields=list(missing),
        language="python",
    )
    new_fields_code = generated.get("generated_code", "")
    # Append to the model file (inside the class, ideally)
    # For simplicity, append at the end of the file
    with open(model_file_path, "a", encoding="utf-8") as f:
        f.write("\n\n" + new_fields_code)
    return True


def merge_and_append_missing_py_schemas(
    schema_file_path: str,
    required_classes: List[str],
    entity_name: str,
    entity_description: str,
    project_id: str = None,
) -> bool:
    """
    Ensures all required schema classes are present in the schema file.
    Only generates and appends missing classes.
    Returns True if any new classes were added, False otherwise.
    """
    if os.path.exists(schema_file_path):
        with open(schema_file_path, "r", encoding="utf-8") as f:
            existing_code = f.read()
    else:
        existing_code = ""

    implemented = set(extract_py_class_names(existing_code))
    missing = set(required_classes) - implemented
    if not missing:
        return False

    generated = LangchainService.generate_schemas_sync(
        project_id=project_id,
        entity_name=entity_name,
        entity_description=entity_description,
        only_classes=list(missing),
        language="python",
    )
    new_classes_code = generated.get("generated_code", "")
    with open(schema_file_path, "a", encoding="utf-8") as f:
        f.write("\n\n" + new_classes_code)
    return True
