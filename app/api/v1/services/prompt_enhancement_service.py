"""
LLM Prompt Enhancement Service (Tier 1)

This service implements intelligent prompt engineering to prevent errors at the source.
It enhances prompts with context, best practices, and error prevention patterns.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class EnhancedPromptResult:
    """Result object for prompt enhancement containing the enhanced prompt and metadata."""

    enhanced_prompt: str
    enhancements_applied: List[str]
    context_injected: bool
    error_prevention_guidelines: List[str]
    original_prompt: str
    enhancement_count: int = 0


class ErrorPatternDatabase:
    """Database of common error patterns and their prevention strategies."""

    def __init__(self):
        self.patterns = {
            "python": {
                "common_errors": [
                    {
                        "pattern": "undefined_variable",
                        "description": "Using variables before definition",
                        "prevention": "Always define variables before use. Use type hints.",
                        "example": "# Bad: result = undefined_var\n# Good: result: str = 'defined_value'",
                    },
                    {
                        "pattern": "import_errors",
                        "description": "Missing or incorrect imports",
                        "prevention": "Import all required modules at the top of the file",
                        "example": "from typing import Optional, Dict, List",
                    },
                    {
                        "pattern": "indentation_errors",
                        "description": "Inconsistent indentation",
                        "prevention": "Use 4 spaces for indentation consistently",
                        "example": "# Use 4 spaces consistently for all indentation levels",
                    },
                    {
                        "pattern": "sql_injection",
                        "description": "Direct string concatenation in SQL queries",
                        "prevention": "Use parameterized queries with SQLAlchemy",
                        "example": "# Bad: query = f'SELECT * FROM users WHERE id = {user_id}'\n# Good: query = session.query(User).filter(User.id == user_id)",
                    },
                    {
                        "pattern": "missing_error_handling",
                        "description": "No exception handling for database operations",
                        "prevention": "Wrap database operations in try-except blocks",
                        "example": "try:\n    result = session.query(Model).all()\nexcept Exception as e:\n    logger.error(f'Database error: {e}')\n    raise",
                    },
                ],
                "best_practices": [
                    "Always use type hints for function parameters and return values",
                    "Include proper error handling with specific exception types",
                    "Use SQLAlchemy ORM methods instead of raw SQL",
                    "Follow PEP 8 style guidelines",
                    "Include docstrings for all functions and classes",
                    "Use f-strings for string formatting",
                    "Import modules at the top of the file",
                    "Use descriptive variable and function names",
                ],
            },
            "javascript": {
                "common_errors": [
                    {
                        "pattern": "undefined_variables",
                        "description": "Using variables before declaration",
                        "prevention": "Always declare variables with const/let",
                        "example": "// Bad: result = someValue\n// Good: const result = someValue",
                    },
                    {
                        "pattern": "async_await_errors",
                        "description": "Missing await for async operations",
                        "prevention": "Always use await for Promise-based operations",
                        "example": "// Bad: const result = asyncFunction()\n// Good: const result = await asyncFunction()",
                    },
                    {
                        "pattern": "null_undefined_errors",
                        "description": "Not handling null/undefined values",
                        "prevention": "Use optional chaining and null checks",
                        "example": "// Use: data?.property || defaultValue",
                    },
                ],
                "best_practices": [
                    "Use const for immutable values, let for variables",
                    "Always handle async operations with try-catch",
                    "Use TypeScript types when available",
                    "Include proper error handling for API calls",
                    "Use modern ES6+ syntax",
                    "Follow consistent naming conventions",
                ],
            },
            "typescript": {
                "common_errors": [
                    {
                        "pattern": "type_errors",
                        "description": "Incorrect or missing type annotations",
                        "prevention": "Use proper TypeScript types and interfaces",
                        "example": "interface User { id: number; name: string; }",
                    },
                    {
                        "pattern": "any_type_overuse",
                        "description": "Overusing 'any' type",
                        "prevention": "Use specific types instead of 'any'",
                        "example": "// Bad: data: any\n// Good: data: User[]",
                    },
                ],
                "best_practices": [
                    "Define interfaces for all data structures",
                    "Use union types for multiple possible types",
                    "Avoid 'any' type unless absolutely necessary",
                    "Use generic types for reusable components",
                    "Enable strict TypeScript compiler options",
                ],
            },
        }

    def get_error_patterns(self, language: str) -> List[Dict]:
        """Get common error patterns for a language."""
        return self.patterns.get(language, {}).get("common_errors", [])

    def get_best_practices(self, language: str) -> List[str]:
        """Get best practices for a language."""
        return self.patterns.get(language, {}).get("best_practices", [])


class PromptEnhancementService:
    """
    Service for enhancing LLM prompts with context, best practices, and error prevention.

    This service implements Tier 1 of the quality strategy by improving prompts
    to prevent errors at the source rather than fixing them later.
    """

    def __init__(self):
        self.error_db = ErrorPatternDatabase()
        self.context_cache = {}

    async def enhance_prompt_for_generation(
        self,
        base_prompt: str,
        language: str,
        component_type: str,
        project_context: Optional[Dict] = None,
        existing_code_patterns: Optional[List[str]] = None,
    ) -> str:
        """
        Enhance a base prompt with context, best practices, and error prevention.

        Args:
            base_prompt: The original user prompt
            language: Programming language (python, javascript, typescript)
            component_type: Type of component being generated (endpoint, model, etc.)
            project_context: Optional project context information
            existing_code_patterns: Optional existing code patterns to follow

        Returns:
            Enhanced prompt with additional context and guidelines
        """
        try:
            enhanced_prompt = base_prompt

            # Add language-specific best practices
            best_practices = self.error_db.get_best_practices(language)
            if best_practices:
                enhanced_prompt += f"\n\n## {language.title()} Best Practices:\n"
                for practice in best_practices:
                    enhanced_prompt += f"- {practice}\n"

            # Add error prevention guidelines
            error_patterns = self.error_db.get_error_patterns(language)
            if error_patterns:
                enhanced_prompt += "\n\n## Error Prevention Guidelines:\n"
                for pattern in error_patterns[:3]:  # Top 3 most common
                    enhanced_prompt += (
                        f"- **{pattern['description']}**: {pattern['prevention']}\n"
                    )

            # Add component-specific guidelines
            component_guidelines = self._get_component_specific_guidelines(
                component_type, language
            )
            if component_guidelines:
                enhanced_prompt += (
                    f"\n\n## {component_type.title()} Specific Guidelines:\n"
                )
                enhanced_prompt += component_guidelines

            # Add project context if available
            if project_context:
                context_info = self._format_project_context(project_context)
                enhanced_prompt += f"\n\n## Project Context:\n{context_info}"

                # Add existing patterns to follow            if existing_code_patterns:
                enhanced_prompt += "\n\n## Follow These Existing Patterns:\n"
                for pattern in existing_code_patterns:
                    enhanced_prompt += f"- {pattern}\n"

            # Add quality requirements
            enhanced_prompt += self._get_quality_requirements(language)

            logger.info(f"Enhanced prompt for {language} {component_type}")
            return enhanced_prompt

        except Exception as e:
            logger.error(f"Error enhancing prompt: {str(e)}", exc_info=True)
            return base_prompt  # Return original if enhancement fails

    def _get_component_specific_guidelines(
        self, component_type: str, language: str
    ) -> str:
        """Get specific guidelines for component types."""
        guidelines = {
            "endpoint": {
                "python": """
- Use FastAPI decorators (@app.get, @app.post, etc.)
- Include proper response models and status codes
- Add comprehensive error handling with HTTPException
- Use dependency injection for database sessions
- Include input validation with Pydantic models
- Add proper logging for debugging
- Use async/await for database operations
- Follow RESTful conventions for URL patterns
                """,
                "javascript": """
- Use Express.js router for endpoint definitions
- Include proper middleware for validation
- Add comprehensive error handling with status codes
- Use async/await for asynchronous operations
- Validate input parameters and body
- Include proper response formatting
- Add request logging for debugging
                """,
                "typescript": """
- Define interfaces for request/response types
- Use Express.js with TypeScript decorators if available
- Include proper type annotations for all parameters
- Add comprehensive error handling with typed errors
- Use async/await with proper type inference
- Validate input with schema validation libraries
                """,
            },
            "model": {
                "python": """
- Use SQLAlchemy ORM with declarative base
- Include proper column types and constraints
- Add relationships using foreign keys
- Include __repr__ method for debugging
- Use proper naming conventions (snake_case for columns)
- Add indexes for frequently queried columns
- Include created_at/updated_at timestamps when relevant
- Use proper data types (Integer, String, DateTime, etc.)
                """,
                "javascript": """
- Use Sequelize or similar ORM for model definitions
- Include proper data types and validations
- Add associations/relationships between models
- Include hooks for data processing
- Use proper naming conventions
- Add indexes for performance
                """,
                "typescript": """
- Define interfaces that match the model structure
- Use TypeORM or Prisma for type-safe database operations
- Include proper type annotations for all fields
- Add validation decorators where appropriate
- Use enums for fixed value sets
                """,
            },
            "schema": {
                "python": """
- Use Pydantic BaseModel for request/response schemas
- Include proper field types and validators
- Add example values for API documentation
- Use Optional for nullable fields
- Include field descriptions for clarity
- Add custom validators for complex validation
- Follow consistent naming conventions
                """,
                "javascript": """
- Use Joi or similar for schema validation
- Include proper validation rules
- Add custom error messages
- Define separate schemas for input/output
- Include default values where appropriate
                """,
                "typescript": """
- Define TypeScript interfaces for all data structures
- Use type unions for multiple possible types
- Include proper optional field markers (?)
- Add JSDoc comments for documentation
- Use generic types for reusable schemas
                """,
            },
        }

        return guidelines.get(component_type, {}).get(language, "")

    def _format_project_context(self, context: Dict) -> str:
        """Format project context information for prompt."""
        formatted = ""

        if context.get("existing_models"):
            formatted += f"Existing models: {', '.join(context['existing_models'])}\n"

        if context.get("database_type"):
            formatted += f"Database: {context['database_type']}\n"

        if context.get("api_version"):
            formatted += f"API Version: {context['api_version']}\n"

        if context.get("dependencies"):
            formatted += f"Dependencies: {', '.join(context['dependencies'])}\n"

        return formatted

    def _get_quality_requirements(self, language: str) -> str:
        """Get quality requirements to add to prompt."""
        return f"""

## Quality Requirements:
- Write clean, readable, and maintainable code
- Include proper error handling and logging
- Follow {language} coding standards and conventions
- Add appropriate comments and docstrings
- Ensure code is production-ready and secure
- Include proper imports and dependencies
- Use consistent formatting and style
- Avoid code duplication and follow DRY principles
- Write testable code with clear separation of concerns
"""

    async def analyze_project_context(self, project_id: str) -> Dict[str, Any]:
        """
        Analyze project context to enhance prompts with relevant information.

        Args:
            project_id: Project identifier

        Returns:
            Dictionary containing project context information
        """
        try:
            # Check cache first
            if project_id in self.context_cache:
                return self.context_cache[project_id]

            project_dir = Path("repos") / project_id
            context = {
                "existing_models": [],
                "existing_endpoints": [],
                "dependencies": [],
                "database_type": None,
                "api_patterns": [],
                "architecture_style": None,
            }

            if not project_dir.exists():
                return context

            # Analyze existing models
            models_dir = project_dir / "models"
            if models_dir.exists():
                for model_file in models_dir.glob("*.py"):
                    model_name = model_file.stem
                    if not model_name.startswith("__"):
                        context["existing_models"].append(model_name)

            # Analyze existing endpoints
            endpoints_dir = project_dir / "endpoints"
            if endpoints_dir.exists():
                for endpoint_file in endpoints_dir.glob("*.py"):
                    endpoint_name = endpoint_file.stem
                    if not endpoint_name.startswith("__"):
                        context["existing_endpoints"].append(endpoint_name)

            # Check for requirements.txt
            requirements_file = project_dir / "requirements.txt"
            if requirements_file.exists():
                with open(requirements_file, "r") as f:
                    context["dependencies"] = [
                        line.split("==")[0].strip()
                        for line in f.readlines()
                        if line.strip() and not line.startswith("#")
                    ]

            # Detect database type
            if "sqlalchemy" in context["dependencies"]:
                context["database_type"] = "SQLAlchemy"
            elif "django" in context["dependencies"]:
                context["database_type"] = "Django ORM"

            # Cache the context
            self.context_cache[project_id] = context

            logger.info(f"Analyzed project context for {project_id}")
            return context

        except Exception as e:
            logger.error(f"Error analyzing project context: {str(e)}", exc_info=True)
            return {}

    async def extract_existing_patterns(
        self, project_id: str, component_type: str
    ) -> List[str]:
        """
        Extract existing code patterns from the project to maintain consistency.

        Args:
            project_id: Project identifier
            component_type: Type of component to analyze patterns for

        Returns:
            List of existing patterns to follow
        """
        try:
            patterns = []
            project_dir = Path("repos") / project_id

            if not project_dir.exists():
                return patterns

            # Map component types to directories
            component_dirs = {
                "endpoint": ["endpoints", "routes", "controllers"],
                "model": ["models"],
                "schema": ["schemas", "serializers"],
                "helpers": ["helpers", "utils"],
            }

            dirs_to_check = component_dirs.get(component_type, [])

            for dir_name in dirs_to_check:
                dir_path = project_dir / dir_name
                if dir_path.exists():
                    patterns.extend(await self._analyze_directory_patterns(dir_path))

            return patterns[:5]  # Return top 5 patterns

        except Exception as e:
            logger.error(f"Error extracting patterns: {str(e)}", exc_info=True)
            return []

    async def _analyze_directory_patterns(self, directory: Path) -> List[str]:
        """Analyze patterns in a directory."""
        patterns = []

        try:
            for file_path in directory.glob("*.py"):
                if file_path.stem.startswith("__"):
                    continue

                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Extract import patterns
                import_pattern = re.findall(
                    r"^from .+ import .+|^import .+", content, re.MULTILINE
                )
                if import_pattern:
                    patterns.append(f"Import pattern: {import_pattern[0]}")

                # Extract class/function patterns
                class_pattern = re.search(r"class (\w+)", content)
                if class_pattern:
                    patterns.append(f"Class naming: {class_pattern.group(1)} pattern")

                # Extract decorator patterns
                decorator_pattern = re.findall(r"@\w+", content)
                if decorator_pattern:
                    patterns.append(
                        f"Uses decorators: {', '.join(set(decorator_pattern))}"
                    )

        except Exception as e:
            logger.error(f"Error analyzing directory {directory}: {str(e)}")

        return patterns

    async def enhance_prompt(
        self,
        original_prompt: str,
        language: str,
        project_dir: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> EnhancedPromptResult:
        """
        Enhanced prompt method that returns structured enhancement result.
        This is the method called by the quality pipeline orchestrator.

        Args:
            original_prompt: The original user prompt
            language: Programming language
            project_dir: Optional project directory for context
            context: Optional context information

        Returns:
            EnhancedPromptResult object with enhancement results
        """
        try:
            # Use the existing enhance_prompt_for_generation method
            enhanced_text = await self.enhance_prompt_for_generation(
                base_prompt=original_prompt,
                language=language,
                component_type=(
                    context.get("component_type", "general") if context else "general"
                ),
                project_context=context,
                existing_code_patterns=(
                    context.get("existing_patterns", []) if context else None
                ),
            )

            # Return structured result expected by pipeline
            return EnhancedPromptResult(
                enhanced_prompt=enhanced_text,
                enhancements_applied=[
                    "Added language-specific best practices",
                    "Added error prevention guidelines",
                    "Added quality requirements",
                    "Added project context" if context else "No project context",
                ],
                context_injected=bool(context),
                error_prevention_guidelines=[
                    "Null pointer/reference prevention",
                    "Type safety guidelines",
                    "Input validation requirements",
                    "Error handling patterns",
                ],
                original_prompt=original_prompt,
                enhancement_count=4 if context else 3,
            )

        except Exception as e:
            logger.error(f"Error in enhance_prompt: {str(e)}", exc_info=True)
            return EnhancedPromptResult(
                enhanced_prompt=original_prompt,
                enhancements_applied=[],
                context_injected=False,
                error_prevention_guidelines=[],
                original_prompt=original_prompt,
                enhancement_count=0,
            )
