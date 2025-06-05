"""
Real-time Validation Service (Tier 2)

This service implements real-time validation during code generation,
providing immediate feedback and correction during the generation process.
"""

import ast
import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ValidationError:
    """Represents a validation error with severity and fix suggestions."""

    def __init__(
        self,
        error_type: str,
        message: str,
        line_number: Optional[int] = None,
        column: Optional[int] = None,
        severity: str = "error",  # error, warning, info
        fix_suggestion: Optional[str] = None,
    ):
        self.error_type = error_type
        self.message = message
        self.line_number = line_number
        self.column = column
        self.severity = severity
        self.fix_suggestion = fix_suggestion

    def to_dict(self) -> Dict:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "line_number": self.line_number,
            "column": self.column,
            "severity": self.severity,
            "fix_suggestion": self.fix_suggestion,
        }


class SyntaxValidator:
    """Validates syntax for different programming languages."""

    def validate_python(self, code: str) -> List[ValidationError]:
        """Validate Python syntax using AST parsing."""
        errors = []

        try:
            # Try to parse the code
            ast.parse(code)
        except SyntaxError as e:
            errors.append(
                ValidationError(
                    error_type="syntax_error",
                    message=f"Syntax error: {e.msg}",
                    line_number=e.lineno,
                    column=e.offset,
                    severity="error",
                    fix_suggestion="Check for missing colons, incorrect indentation, or unmatched brackets",
                )
            )
        except Exception as e:
            errors.append(
                ValidationError(
                    error_type="parse_error",
                    message=f"Parse error: {str(e)}",
                    severity="error",
                )
            )

        return errors

    def validate_javascript(self, code: str) -> List[ValidationError]:
        """Validate JavaScript syntax (basic validation)."""
        errors = []

        # Basic bracket matching
        bracket_errors = self._check_bracket_matching(code)
        errors.extend(bracket_errors)

        # Check for common JS syntax issues
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            line = line.strip()

            # Check for missing semicolons (basic check)
            if (
                line
                and not line.endswith((";", "{", "}", ")", ","))
                and not line.startswith(
                    ("if", "for", "while", "function", "class", "//", "/*", "*")
                )
            ):
                errors.append(
                    ValidationError(
                        error_type="missing_semicolon",
                        message="Consider adding semicolon",
                        line_number=i,
                        severity="warning",
                        fix_suggestion="Add semicolon at end of statement",
                    )
                )

            # Check for undefined variables (basic)
            if re.search(r"\b\w+\s*=\s*\w+\b", line) and not any(
                keyword in line for keyword in ["const", "let", "var"]
            ):
                if not re.search(r"\.|\[|\(", line):  # Not property access
                    errors.append(
                        ValidationError(
                            error_type="undeclared_variable",
                            message="Possible undeclared variable assignment",
                            line_number=i,
                            severity="warning",
                            fix_suggestion="Declare variable with const, let, or var",
                        )
                    )

        return errors

    def validate_typescript(self, code: str) -> List[ValidationError]:
        """Validate TypeScript syntax (basic validation)."""
        errors = []

        # Start with JavaScript validation
        errors.extend(self.validate_javascript(code))

        # Additional TypeScript-specific checks
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            line = line.strip()

            # Check for 'any' type usage
            if ": any" in line or "<any>" in line:
                errors.append(
                    ValidationError(
                        error_type="any_type_usage",
                        message="Avoid using 'any' type when possible",
                        line_number=i,
                        severity="warning",
                        fix_suggestion="Use specific types instead of 'any'",
                    )
                )

            # Check for interface naming (should start with uppercase)
            interface_match = re.search(r"interface\s+([a-z]\w*)", line)
            if interface_match:
                errors.append(
                    ValidationError(
                        error_type="interface_naming",
                        message=f"Interface '{interface_match.group(1)}' should start with uppercase",
                        line_number=i,
                        severity="warning",
                        fix_suggestion="Use PascalCase for interface names",
                    )
                )

        return errors

    def _check_bracket_matching(self, code: str) -> List[ValidationError]:
        """Check for matching brackets, parentheses, and braces."""
        errors = []
        stack = []
        pairs = {"(": ")", "[": "]", "{": "}"}

        lines = code.split("\n")
        for line_num, line in enumerate(lines, 1):
            for col, char in enumerate(line):
                if char in pairs:
                    stack.append((char, line_num, col))
                elif char in pairs.values():
                    if not stack:
                        errors.append(
                            ValidationError(
                                error_type="unmatched_bracket",
                                message=f"Unmatched closing bracket: {char}",
                                line_number=line_num,
                                column=col,
                                severity="error",
                                fix_suggestion="Add matching opening bracket",
                            )
                        )
                    else:
                        opening_char, _, _ = stack.pop()
                        if pairs[opening_char] != char:
                            errors.append(
                                ValidationError(
                                    error_type="mismatched_bracket",
                                    message=f"Mismatched brackets: {opening_char} and {char}",
                                    line_number=line_num,
                                    column=col,
                                    severity="error",
                                    fix_suggestion="Fix bracket pairing",
                                )
                            )

        # Check for unclosed brackets
        for opening_char, line_num, col in stack:
            errors.append(
                ValidationError(
                    error_type="unclosed_bracket",
                    message=f"Unclosed bracket: {opening_char}",
                    line_number=line_num,
                    column=col,
                    severity="error",
                    fix_suggestion=f"Add closing bracket: {pairs[opening_char]}",
                )
            )

        return errors


class ConstraintValidator:
    """Validates code against architectural and project constraints."""

    def __init__(self):
        self.constraints = {
            "python": {
                "required_imports": {
                    "endpoint": ["fastapi", "pydantic"],
                    "model": ["sqlalchemy"],
                    "schema": ["pydantic"],
                },
                "forbidden_patterns": [
                    r"exec\s*\(",  # Dangerous exec calls
                    r"eval\s*\(",  # Dangerous eval calls
                    r"__import__\s*\(",  # Dynamic imports
                ],
                "required_patterns": {
                    "endpoint": [r"@app\.(get|post|put|delete|patch)"],
                    "model": [r"class\s+\w+\s*\(.*Base.*\)"],
                    "schema": [r"class\s+\w+\s*\(.*BaseModel.*\)"],
                },
            },
            "javascript": {
                "forbidden_patterns": [
                    r"eval\s*\(",  # Dangerous eval calls
                    r"innerHTML\s*=",  # XSS vulnerability
                ],
                "required_patterns": {
                    "endpoint": [r"router\.(get|post|put|delete|patch)"],
                },
            },
        }

    def validate_constraints(
        self,
        code: str,
        language: str,
        component_type: str,
        project_context: Optional[Dict] = None,
    ) -> List[ValidationError]:
        """Validate code against defined constraints."""
        errors = []

        language_constraints = self.constraints.get(language, {})

        # Check forbidden patterns
        forbidden = language_constraints.get("forbidden_patterns", [])
        for pattern in forbidden:
            if re.search(pattern, code, re.IGNORECASE):
                errors.append(
                    ValidationError(
                        error_type="forbidden_pattern",
                        message=f"Forbidden pattern detected: {pattern}",
                        severity="error",
                        fix_suggestion="Remove or replace the forbidden pattern",
                    )
                )

        # Check required patterns for component type
        required = language_constraints.get("required_patterns", {}).get(
            component_type, []
        )
        for pattern in required:
            if not re.search(pattern, code, re.IGNORECASE):
                errors.append(
                    ValidationError(
                        error_type="missing_required_pattern",
                        message=f"Missing required pattern for {component_type}: {pattern}",
                        severity="warning",
                        fix_suggestion=f"Add required pattern for {component_type}",
                    )
                )

        # Check required imports
        required_imports = language_constraints.get("required_imports", {}).get(
            component_type, []
        )
        for required_import in required_imports:
            if not re.search(rf"(from|import).*{required_import}", code, re.IGNORECASE):
                errors.append(
                    ValidationError(
                        error_type="missing_import",
                        message=f"Missing required import: {required_import}",
                        severity="warning",
                        fix_suggestion=f"Add import for {required_import}",
                    )
                )

        return errors

    def validate_database_consistency(
        self, model_code: str, existing_models: List[str]
    ) -> List[ValidationError]:
        """Validate database schema consistency."""
        errors = []

        # Extract foreign key references from the model
        fk_pattern = r"ForeignKey\s*\(\s*['\"](\w+)\.(\w+)['\"]"
        fk_matches = re.findall(fk_pattern, model_code)

        for table_name, column_name in fk_matches:
            # Convert table name to model name (basic conversion)
            model_name = "".join(word.capitalize() for word in table_name.split("_"))

            if model_name.lower() not in [m.lower() for m in existing_models]:
                errors.append(
                    ValidationError(
                        error_type="missing_referenced_model",
                        message=f"Foreign key references non-existent model: {model_name}",
                        severity="error",
                        fix_suggestion=f"Create the {model_name} model or remove the foreign key",
                    )
                )

        return errors


class RealTimeValidationService:
    """
    Main service for real-time validation during code generation.

    This service implements Tier 2 of the quality strategy by providing
    immediate feedback during the generation process.
    """

    def __init__(self):
        self.syntax_validator = SyntaxValidator()
        self.constraint_validator = ConstraintValidator()
        self.validation_cache = {}

    async def validate_generated_code(
        self,
        code: str,
        language: str,
        component_type: str,
        project_context: Optional[Dict] = None,
        incremental: bool = False,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive real-time validation of generated code.

        Args:
            code: The generated code to validate
            language: Programming language
            component_type: Type of component (endpoint, model, etc.)
            project_context: Optional project context for constraint validation
            incremental: Whether this is incremental validation

        Returns:
            Validation result with errors, warnings, and suggestions
        """
        try:
            validation_result = {
                "valid": True,
                "errors": [],
                "warnings": [],
                "info": [],
                "fix_suggestions": [],
                "quality_score": 100,
                "validation_time": 0,
            }

            start_time = asyncio.get_event_loop().time()

            # 1. Syntax validation
            syntax_errors = await self._validate_syntax(code, language)
            validation_result["errors"].extend(
                [e for e in syntax_errors if e.severity == "error"]
            )
            validation_result["warnings"].extend(
                [e for e in syntax_errors if e.severity == "warning"]
            )

            # 2. Constraint validation
            constraint_errors = await self._validate_constraints(
                code, language, component_type, project_context
            )
            validation_result["errors"].extend(
                [e for e in constraint_errors if e.severity == "error"]
            )
            validation_result["warnings"].extend(
                [e for e in constraint_errors if e.severity == "warning"]
            )

            # 3. Database consistency validation (for models)
            if component_type == "model" and project_context:
                db_errors = await self._validate_database_consistency(
                    code, project_context.get("existing_models", [])
                )
                validation_result["errors"].extend(
                    [e for e in db_errors if e.severity == "error"]
                )
                validation_result["warnings"].extend(
                    [e for e in db_errors if e.severity == "warning"]
                )

            # 4. Best practices validation
            best_practice_issues = await self._validate_best_practices(
                code, language, component_type
            )
            validation_result["info"].extend(best_practice_issues)

            # 5. Generate fix suggestions
            validation_result["fix_suggestions"] = await self._generate_fix_suggestions(
                validation_result["errors"] + validation_result["warnings"]
            )

            # 6. Calculate quality score
            validation_result["quality_score"] = self._calculate_quality_score(
                len(validation_result["errors"]),
                len(validation_result["warnings"]),
                len(validation_result["info"]),
            )

            # Set overall validity
            validation_result["valid"] = len(validation_result["errors"]) == 0

            # Record validation time
            end_time = asyncio.get_event_loop().time()
            validation_result["validation_time"] = end_time - start_time

            # Convert ValidationError objects to dictionaries
            validation_result["errors"] = [
                e.to_dict() for e in validation_result["errors"]
            ]
            validation_result["warnings"] = [
                e.to_dict() for e in validation_result["warnings"]
            ]
            validation_result["info"] = [e.to_dict() for e in validation_result["info"]]

            logger.info(
                f"Validation completed: {validation_result['quality_score']} score, "
                f"{len(validation_result['errors'])} errors, "
                f"{len(validation_result['warnings'])} warnings"
            )

            return validation_result

        except Exception as e:
            logger.error(f"Error in real-time validation: {str(e)}", exc_info=True)
            return {
                "valid": False,
                "errors": [{"error_type": "validation_failure", "message": str(e)}],
                "warnings": [],
                "info": [],
                "fix_suggestions": [],
                "quality_score": 0,
                "validation_time": 0,
            }

    async def _validate_syntax(self, code: str, language: str) -> List[ValidationError]:
        """Validate syntax for the given language."""
        if language == "python":
            return self.syntax_validator.validate_python(code)
        elif language == "javascript":
            return self.syntax_validator.validate_javascript(code)
        elif language == "typescript":
            return self.syntax_validator.validate_typescript(code)
        else:
            return []

    async def _validate_constraints(
        self,
        code: str,
        language: str,
        component_type: str,
        project_context: Optional[Dict],
    ) -> List[ValidationError]:
        """Validate architectural and project constraints."""
        return self.constraint_validator.validate_constraints(
            code, language, component_type, project_context
        )

    async def _validate_database_consistency(
        self, code: str, existing_models: List[str]
    ) -> List[ValidationError]:
        """Validate database schema consistency."""
        return self.constraint_validator.validate_database_consistency(
            code, existing_models
        )

    async def _validate_best_practices(
        self, code: str, language: str, component_type: str
    ) -> List[ValidationError]:
        """Validate against best practices."""
        issues = []
        lines = code.split("\n")

        if language == "python":
            for i, line in enumerate(lines, 1):
                line = line.strip()

                # Check for TODO comments
                if "TODO" in line.upper():
                    issues.append(
                        ValidationError(
                            error_type="todo_comment",
                            message="TODO comment found",
                            line_number=i,
                            severity="info",
                            fix_suggestion="Complete the TODO or remove the comment",
                        )
                    )

                # Check for print statements (should use logging)
                if re.search(r"\bprint\s*\(", line):
                    issues.append(
                        ValidationError(
                            error_type="print_statement",
                            message="Consider using logging instead of print",
                            line_number=i,
                            severity="info",
                            fix_suggestion="Replace print with logger.info() or similar",
                        )
                    )

                # Check for missing docstrings in functions/classes
                if re.search(r"^\s*(def|class)\s+\w+", line):
                    # Check if next non-empty line is a docstring
                    for j in range(i, min(i + 3, len(lines))):
                        next_line = lines[j].strip()
                        if (
                            next_line
                            and not next_line.startswith('"""')
                            and not next_line.startswith("'''")
                        ):
                            issues.append(
                                ValidationError(
                                    error_type="missing_docstring",
                                    message="Consider adding a docstring",
                                    line_number=i,
                                    severity="info",
                                    fix_suggestion="Add a descriptive docstring",
                                )
                            )
                            break
                        elif next_line.startswith('"""') or next_line.startswith("'''"):
                            break

        return issues

    async def _generate_fix_suggestions(
        self, errors: List[ValidationError]
    ) -> List[str]:
        """Generate actionable fix suggestions based on errors."""
        suggestions = []

        for error in errors:
            if error.fix_suggestion:
                suggestions.append(f"{error.error_type}: {error.fix_suggestion}")

        # Add general suggestions
        if any(e.error_type == "syntax_error" for e in errors):
            suggestions.append(
                "Run the code through a syntax checker or IDE for detailed error locations"
            )

        if any(e.error_type == "missing_import" for e in errors):
            suggestions.append(
                "Review and add all required imports at the top of the file"
            )

        return list(set(suggestions))  # Remove duplicates

    def _calculate_quality_score(
        self, error_count: int, warning_count: int, info_count: int
    ) -> int:
        """Calculate a quality score based on validation results."""
        base_score = 100

        # Deduct points for errors and warnings
        score = base_score - (error_count * 20) - (warning_count * 5) - (info_count * 1)

        # Ensure score is between 0 and 100
        return max(0, min(100, score))

    async def validate_code_stream(
        self,
        code_stream: str,
        language: str,
        component_type: str,
        project_context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Validate code as it's being generated (streaming validation).

        This method is designed for real-time validation during generation.
        """
        try:
            # For streaming, we do lighter validation to avoid blocking
            validation_result = {
                "valid": True,
                "syntax_valid": True,
                "current_issues": [],
                "partial_score": 100,
            }

            # Quick syntax check
            if language == "python":
                try:
                    # Try to parse what we have so far
                    ast.parse(code_stream)
                    validation_result["syntax_valid"] = True
                except SyntaxError:
                    # Check if it's just incomplete (common during streaming)
                    if code_stream.strip().endswith((":", "(", "[", "{")):
                        validation_result["syntax_valid"] = (
                            True  # Incomplete but valid so far
                        )
                    else:
                        validation_result["syntax_valid"] = False
                        validation_result["current_issues"].append(
                            "Syntax error detected"
                        )

            # Quick constraint check
            constraint_errors = await self._validate_constraints(
                code_stream, language, component_type, project_context
            )

            critical_errors = [e for e in constraint_errors if e.severity == "error"]
            if critical_errors:
                validation_result["valid"] = False
                validation_result["current_issues"].extend(
                    [e.message for e in critical_errors]
                )

            # Calculate partial score
            issue_count = len(validation_result["current_issues"])
            validation_result["partial_score"] = max(0, 100 - (issue_count * 10))

            return validation_result

        except Exception as e:
            logger.error(f"Error in stream validation: {str(e)}")
            return {
                "valid": False,
                "syntax_valid": False,
                "current_issues": [f"Validation error: {str(e)}"],
                "partial_score": 0,
            }

    async def validate_code_streaming(
        self, code: str, language: str, file_path: str, incremental: bool = False
    ) -> Dict[str, Any]:
        """
        Streaming validation method that returns structured validation results.
        This is the method called by the quality pipeline orchestrator.

        Args:
            code: The code to validate
            language: Programming language
            file_path: Path to the file being validated
            incremental: Whether this is incremental validation

        Returns:
            Dictionary with validation results
        """
        try:
            # Use the existing validate_generated_code method
            validation_result = await self.validate_generated_code(
                code=code,
                language=language,
                component_type=self._detect_component_type(file_path),
                project_context=None,
                incremental=incremental,
            )

            # Transform to expected format for pipeline
            return {
                "errors": validation_result.get("errors", []),
                "warnings": validation_result.get("warnings", []),
                "suggestions": validation_result.get("fix_suggestions", []),
                "syntax_valid": validation_result.get("valid", True),
                "syntax_errors": len(
                    [
                        e
                        for e in validation_result.get("errors", [])
                        if e.get("error_type") == "syntax_error"
                    ]
                ),
                "style_violations": len(
                    [
                        e
                        for e in validation_result.get("warnings", [])
                        if "style" in e.get("error_type", "")
                    ]
                ),
                "security_issues": len(
                    [
                        e
                        for e in validation_result.get("errors", [])
                        if "security" in e.get("error_type", "")
                    ]
                ),
                "complexity_issues": len(
                    [
                        e
                        for e in validation_result.get("warnings", [])
                        if "complexity" in e.get("error_type", "")
                    ]
                ),
                "constraint_violations": [
                    e
                    for e in validation_result.get("errors", [])
                    if "constraint" in e.get("error_type", "")
                ],
                "quality_score": validation_result.get("quality_score", 100),
                "validation_time": validation_result.get("validation_time", 0),
                "success": True,
            }

        except Exception as e:
            logger.error(f"Error in validate_code_streaming: {str(e)}", exc_info=True)
            return {
                "errors": [{"error_type": "validation_failure", "message": str(e)}],
                "warnings": [],
                "suggestions": [],
                "syntax_valid": False,
                "syntax_errors": 1,
                "style_violations": 0,
                "security_issues": 0,
                "complexity_issues": 0,
                "constraint_violations": [],
                "quality_score": 0,
                "validation_time": 0,
                "success": False,
                "error": str(e),
            }

    def _detect_component_type(self, file_path: str) -> str:
        """Detect component type from file path."""
        file_path_lower = file_path.lower()

        if "model" in file_path_lower:
            return "model"
        elif (
            "endpoint" in file_path_lower
            or "route" in file_path_lower
            or "api" in file_path_lower
        ):
            return "endpoint"
        elif "schema" in file_path_lower:
            return "schema"
        elif "helper" in file_path_lower or "util" in file_path_lower:
            return "helper"
        else:
            return "general"

    # ...existing code...
