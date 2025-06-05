"""
Mock implementations for language template factory and related classes for testing.
"""

from typing import Any


class LanguageTemplateFactory:
    """Mock implementation of LanguageTemplateFactory for testing."""

    @staticmethod
    def create_template(language: str, **kwargs) -> Any:
        """
        Create a language template instance for the specified language.
        This is a mock implementation for testing.

        Args:
            language: The programming language
            **kwargs: Additional parameters for template creation

        Returns:
            MockLanguageTemplate: A mock language template instance
        """
        from tests.v1.code_generation.test_incremental_code_generation import (
            MockLanguageTemplate,
        )

        return MockLanguageTemplate(language=language)
