"""
Language Templates Package

This package contains the templates for generating code in different programming languages.
Each language has its own template class that implements the LanguageTemplate abstract base class.
"""

from app.api.v1.services.language_templates.language_template import (
    LanguageTemplate,
    LanguageTemplateFactory
)

# Import all language templates to ensure they're registered with the factory
from app.api.v1.services.language_templates.python_template import PythonTemplate
from app.api.v1.services.language_templates.javascript_template import JavaScriptTemplate

# Register all templates with the factory
LanguageTemplateFactory.register_template("python", PythonTemplate)
LanguageTemplateFactory.register_template("javascript", JavaScriptTemplate)
LanguageTemplateFactory.register_template("js", JavaScriptTemplate)

__all__ = [
    "LanguageTemplate",
    "LanguageTemplateFactory",
    "PythonTemplate",
    "JavaScriptTemplate",
]