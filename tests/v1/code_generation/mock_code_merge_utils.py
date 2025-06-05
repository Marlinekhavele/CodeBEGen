"""
Mock implementations of code merge utilities for testing.
"""

import re
from typing import List


def extract_py_function_names(code: str) -> List[str]:
    """Extract Python function names from code."""
    pattern = r"def\s+([a-zA-Z0-9_]+)\s*\("
    matches = re.findall(pattern, code)
    return matches


def extract_required_py_helpers_from_endpoint(endpoint_code: str) -> List[str]:
    """Extract required helper function names from endpoint code."""
    # Look for function names in import statements like: from helpers.xxx import func1, func2
    helper_import_pattern = r"from\s+helpers\.[a-zA-Z0-9_]+\s+import\s+([^()]+)"
    import_matches = re.findall(helper_import_pattern, endpoint_code)

    functions = []
    for match in import_matches:
        functions.extend([f.strip() for f in match.split(",") if f.strip()])

    # Return unique function names
    return list(set(functions))


def extract_js_function_names(code: str) -> List[str]:
    """Extract JavaScript function names from code."""
    # Simple pattern for both function declarations and arrow functions
    pattern = r"(function\s+([a-zA-Z0-9_]+)|const\s+([a-zA-Z0-9_]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)"
    matches = re.findall(pattern, code)

    functions = []
    for match in matches:
        if match[1]:  # Regular function
            functions.append(match[1])
        elif match[2]:  # Arrow function
            functions.append(match[2])

    return functions


def extract_required_js_helpers_from_endpoint(endpoint_code: str) -> List[str]:
    """Extract required helper function names from endpoint code."""
    # Look for function names in require/import statements
    helper_import_pattern = r"(?:require|import)\s*\(\s*['\"]helpers/([^'\"]+)['\"]"
    import_matches = re.findall(helper_import_pattern, endpoint_code)

    functions = []
    for match in import_matches:
        functions.append(match)

    # Return unique function names
    return list(set(functions))
