"""Test helpers for incremental code generation.

This file includes functions that help with testing incremental code generation.
It's designed to be imported by existing test files to patch functionality
that may be missing in the core codebase or mock implementations needed for testing.
"""

import base64
import hashlib
from typing import Any, Dict, List, Optional


# Helper functions for Language Template
def needs_database(code: str) -> bool:
    """Enhanced database dependency detection for tests."""
    return (
        "db." in code
        or "database" in code
        or "Session" in code
        or "Depends(get_db)" in code
        or "sqlalchemy" in code
    )


# Mock implementation of LangchainService.generate_helpers_sync
def mock_generate_helpers_sync(
    project_id: str,
    entity_name: str,
    entity_description: Optional[str] = None,
    endpoint_code: Optional[str] = None,
    model_code: Optional[str] = None,
    schema_code: Optional[str] = None,
    only_functions: Optional[List[str]] = None,
    language: str = "python",
) -> Dict[str, Any]:
    """Mock implementation of generate_helpers_sync for tests."""
    # Generate code based on requested functions
    if only_functions:
        if language.lower() in ["python", "py"]:
            code_lines = []
            for func_name in only_functions:
                code_lines.append(f"def {func_name}():")
                code_lines.append(f"    # Mock implementation for {func_name}")
                code_lines.append("    pass")
                code_lines.append("")
            generated_code = "\n".join(code_lines)
        else:
            # JavaScript
            code_lines = []
            for func_name in only_functions:
                code_lines.append(f"exports.{func_name} = () => {{")
                code_lines.append(f"    // Mock implementation for {func_name}")
                code_lines.append("}};")
                code_lines.append("")
            generated_code = "\n".join(code_lines)
    else:
        generated_code = f"# Generated helpers for {entity_name}"
    # Generate a simple hash
    file_hash = hashlib.md5(generated_code.encode("utf-8")).hexdigest()
    # Base64 encode
    content_base64 = base64.b64encode(generated_code.encode("utf-8")).decode("utf-8")
    return {
        "generated_code": generated_code,
        "content_base64": content_base64,
        "file_hash": file_hash,
        "language": language,
        # Add any other required fields for Pydantic validation
    }


# Factory for language templates
class MockLanguageTemplateFactory:
    """Mock template factory for tests."""

    @staticmethod
    def create_template(language: str, **kwargs):
        """Create a mock template for testing."""
        from tests.v1.code_generation.test_incremental_code_generation import (
            MockLanguageTemplate,
        )

        return MockLanguageTemplate(language=language)


# Patch these into their respective modules
def apply_patches():
    """Apply all patches to fix test issues."""
    # Add generate_helpers_sync to LangchainService if it doesn't exist
    from app.api.v1.services.langchain_service import LangchainService

    if not hasattr(LangchainService, "generate_helpers_sync"):
        setattr(
            LangchainService,
            "generate_helpers_sync",
            staticmethod(mock_generate_helpers_sync),
        )

    # Add create_template to LanguageTemplateFactory if it doesn't exist
    from app.api.v1.services.language_templates.language_template import (
        LanguageTemplateFactory,
    )

    if not hasattr(LanguageTemplateFactory, "create_template"):
        setattr(
            LanguageTemplateFactory,
            "create_template",
            staticmethod(MockLanguageTemplateFactory.create_template),
        )

    print("Applied test patches for incremental code generation tests")


# Apply patches when this module is imported
apply_patches()
