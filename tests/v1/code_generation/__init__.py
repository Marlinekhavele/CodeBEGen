# Mock imports for testing
class LanguageTemplateFactory:
    """Mock implementation of LanguageTemplateFactory for testing."""

    @staticmethod
    def create_template(language: str, **kwargs):
        """Create a template for the specified language."""
        from tests.v1.code_generation.test_incremental_code_generation import (
            MockLanguageTemplate,
        )

        return MockLanguageTemplate(language=language)
