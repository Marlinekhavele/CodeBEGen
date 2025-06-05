"""
Enhanced Code Quality Service (Tier 3) - Advanced Auto-fixing and Quality Improvement

This enhanced service builds upon the existing CodeQualityService and integrates
with the new Tier 1, 2, and 4 services to provide comprehensive auto-fixing
capabilities and quality improvements.
"""

import ast
import asyncio
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .prompt_enhancement_service import PromptEnhancementService
from .real_time_validation_service import RealTimeValidationService, ValidationError
from .semantic_validation_service import SemanticValidationService

logger = logging.getLogger(__name__)


class AutoFixStrategy(Enum):
    """Strategies for automatically fixing code issues."""

    CONSERVATIVE = "conservative"  # Only apply safe, proven fixes
    MODERATE = "moderate"  # Apply most fixes with moderate risk
    AGGRESSIVE = "aggressive"  # Apply all available fixes


@dataclass
class EnhancedQualityReport:
    """Enhanced quality report with detailed analysis."""

    original_code: str
    fixed_code: str
    quality_score: float

    # Issue tracking
    issues_found: List[Dict[str, Any]]
    issues_fixed: List[Dict[str, Any]]
    remaining_issues: List[Dict[str, Any]]

    # Validation results
    syntax_validation: Dict[str, Any]
    semantic_validation: Dict[str, Any]
    security_analysis: Dict[str, Any]
    performance_analysis: Dict[str, Any]

    # Auto-fixing results
    auto_fixes_applied: List[Dict[str, Any]]
    manual_fixes_suggested: List[Dict[str, Any]]

    # Metrics
    complexity_metrics: Dict[str, float]
    maintainability_score: float
    reliability_score: float

    # Execution info
    tools_used: List[str]
    execution_time: float
    fix_strategy: AutoFixStrategy


class EnhancedCodeQualityService:
    """Enhanced code quality service with advanced auto-fixing capabilities."""

    def __init__(self):
        # Initialize tier services
        self.prompt_enhancer = PromptEnhancementService()
        self.real_time_validator = RealTimeValidationService()
        self.semantic_validator = SemanticValidationService()

        # Auto-fixing patterns and rules
        self.auto_fix_patterns = self._initialize_auto_fix_patterns()
        self.quality_thresholds = self._initialize_quality_thresholds()

    async def enhance_code_quality(
        self,
        code: str,
        file_path: str,
        language: str = "python",
        project_dir: Optional[str] = None,
        fix_strategy: AutoFixStrategy = AutoFixStrategy.MODERATE,
        context: Optional[Dict[str, Any]] = None,
    ) -> EnhancedQualityReport:
        """
        Comprehensive code quality enhancement with advanced auto-fixing.

        Args:
            code: Source code to enhance
            file_path: File path for context
            language: Programming language
            project_dir: Project directory for context
            fix_strategy: Auto-fix strategy to apply
            context: Additional context for quality improvement

        Returns:
            EnhancedQualityReport with comprehensive analysis and fixes
        """
        start_time = asyncio.get_event_loop().time()
        original_code = code
        current_code = code
        tools_used = []

        try:
            logger.info(f"Starting enhanced quality improvement for {file_path}")

            # Phase 1: Real-time validation
            validation_result = await self.real_time_validator.validate_code_streaming(
                code=current_code, language=language, file_path=file_path
            )

            # Phase 2: Apply automatic fixes based on validation results
            current_code, auto_fixes = await self._apply_automatic_fixes(
                code=current_code,
                validation_errors=validation_result.get("errors", []),
                language=language,
                strategy=fix_strategy,
            )

            # Phase 3: Advanced formatting and optimization
            current_code, formatting_fixes = await self._apply_advanced_formatting(
                code=current_code, language=language, file_path=file_path
            )

            # Phase 4: Semantic enhancement
            semantic_result = await self.semantic_validator.validate_code_comprehensive(
                code=current_code,
                language=language,
                file_path=file_path,
                project_dir=project_dir,
            )

            # Phase 5: Apply semantic fixes
            current_code, semantic_fixes = await self._apply_semantic_fixes(
                code=current_code,
                semantic_analysis=semantic_result,
                language=language,
                strategy=fix_strategy,
            )

            # Phase 6: Performance optimizations
            current_code, performance_fixes = (
                await self._apply_performance_optimizations(
                    code=current_code, language=language, strategy=fix_strategy
                )
            )

            # Phase 7: Security hardening
            current_code, security_fixes = await self._apply_security_hardening(
                code=current_code, language=language, strategy=fix_strategy
            )

            # Phase 8: Final validation
            final_validation = await self.real_time_validator.validate_code_streaming(
                code=current_code, language=language, file_path=file_path
            )

            # Calculate quality metrics
            quality_score = self._calculate_quality_score(
                current_code, language, final_validation, semantic_result
            )
            complexity_metrics = self._calculate_complexity_metrics(
                current_code, language
            )

            # Compile results
            all_fixes = (
                auto_fixes
                + formatting_fixes
                + semantic_fixes
                + performance_fixes
                + security_fixes
            )
            issues_fixed = [fix for fix in all_fixes if fix.get("applied", False)]
            manual_suggestions = [
                fix for fix in all_fixes if not fix.get("applied", False)
            ]

            execution_time = asyncio.get_event_loop().time() - start_time

            return EnhancedQualityReport(
                original_code=original_code,
                fixed_code=current_code,
                quality_score=quality_score,
                issues_found=validation_result.get("errors", [])
                + semantic_result.get("issues", []),
                issues_fixed=issues_fixed,
                remaining_issues=final_validation.get("errors", []),
                syntax_validation=validation_result,
                semantic_validation=semantic_result,
                security_analysis=semantic_result.get("security_analysis", {}),
                performance_analysis=semantic_result.get("performance_analysis", {}),
                auto_fixes_applied=issues_fixed,
                manual_fixes_suggested=manual_suggestions,
                complexity_metrics=complexity_metrics,
                maintainability_score=self._calculate_maintainability_score(
                    current_code, language
                ),
                reliability_score=self._calculate_reliability_score(
                    final_validation, semantic_result
                ),
                tools_used=tools_used,
                execution_time=execution_time,
                fix_strategy=fix_strategy,
            )

        except Exception as e:
            logger.error(
                f"Error in enhanced quality improvement: {str(e)}", exc_info=True
            )
            execution_time = asyncio.get_event_loop().time() - start_time

            # Return minimal report on error
            return EnhancedQualityReport(
                original_code=original_code,
                fixed_code=current_code,
                quality_score=0.0,
                issues_found=[{"error": str(e), "severity": "critical"}],
                issues_fixed=[],
                remaining_issues=[{"error": str(e), "severity": "critical"}],
                syntax_validation={},
                semantic_validation={},
                security_analysis={},
                performance_analysis={},
                auto_fixes_applied=[],
                manual_fixes_suggested=[],
                complexity_metrics={},
                maintainability_score=0.0,
                reliability_score=0.0,
                tools_used=tools_used,
                execution_time=execution_time,
                fix_strategy=fix_strategy,
            )

    async def _apply_automatic_fixes(
        self,
        code: str,
        validation_errors: List[ValidationError],
        language: str,
        strategy: AutoFixStrategy,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Apply automatic fixes based on validation errors."""
        current_code = code
        fixes_applied = []
        for error in validation_errors:
            # Handle both ValidationError objects and dictionaries
            if isinstance(error, dict):
                error_severity = error.get("severity", "unknown")
            else:
                error_severity = getattr(error, "severity", "unknown")

            if (
                error_severity in ["critical", "high", "error"]
                or strategy == AutoFixStrategy.AGGRESSIVE
            ):
                # Attempt to fix the error
                fixed_code, fix_result = await self._fix_validation_error(
                    current_code, error, language, strategy
                )

                if fix_result["success"]:
                    current_code = fixed_code
                    fixes_applied.append(
                        {
                            **fix_result,
                            "error_type": (
                                error.error_type
                                if hasattr(error, "error_type")
                                else error.get("error_type", "unknown")
                            ),
                            "original_message": (
                                error.message
                                if hasattr(error, "message")
                                else error.get("message", "No message")
                            ),
                            "applied": True,
                        }
                    )
                else:
                    fixes_applied.append(
                        {
                            **fix_result,
                            "error_type": (
                                error.error_type
                                if hasattr(error, "error_type")
                                else error.get("error_type", "unknown")
                            ),
                            "original_message": (
                                error.message
                                if hasattr(error, "message")
                                else error.get("message", "No message")
                            ),
                            "applied": False,
                        }
                    )

        return current_code, fixes_applied

    async def _fix_validation_error(
        self,
        code: str,
        error: ValidationError,
        language: str,
        strategy: AutoFixStrategy,
    ) -> Tuple[str, Dict[str, Any]]:
        """Fix a specific validation error."""
        if language == "python":
            return await self._fix_python_error(code, error, strategy)
        elif language in ["javascript", "typescript"]:
            return await self._fix_js_error(code, error, strategy)
        else:
            return code, {
                "success": False,
                "reason": f"Unsupported language: {language}",
            }

    async def _fix_python_error(
        self, code: str, error: ValidationError, strategy: AutoFixStrategy
    ) -> Tuple[str, Dict[str, Any]]:
        """Fix Python-specific errors."""
        # Handle both ValidationError objects and dictionaries
        if hasattr(error, "error_type"):
            error_type = error.error_type
        else:
            error_type = error.get("error_type", "unknown")

        if error_type == "undefined_variable":
            return await self._fix_undefined_variable(code, error, strategy)
        elif error_type == "import_error":
            return await self._fix_import_error(code, error, strategy)
        elif error_type == "syntax_error":
            return await self._fix_syntax_error(code, error, strategy)
        elif error_type == "indentation_error":
            return await self._fix_indentation_error(code, error, strategy)
        elif error_type == "type_error":
            return await self._fix_type_error(code, error, strategy)
        else:
            return code, {
                "success": False,
                "reason": f"No fix available for {error_type}",
            }

    async def _fix_undefined_variable(
        self, code: str, error: ValidationError, strategy: AutoFixStrategy
    ) -> Tuple[str, Dict[str, Any]]:
        """Fix undefined variable errors."""
        try:
            # Extract variable name from error message
            error_message = (
                error.message if hasattr(error, "message") else error.get("message", "")
            )
            var_match = re.search(r"name '(\w+)' is not defined", error_message)
            if not var_match:
                return code, {
                    "success": False,
                    "reason": "Could not extract variable name",
                }

            var_name = var_match.group(1)

            # Common fix patterns
            if var_name.isupper():
                # Likely a constant, add it at the top
                fixed_code = (
                    f"{var_name} = None  # TODO: Define this constant\n\n{code}"
                )
                return fixed_code, {
                    "success": True,
                    "fix_type": "add_constant_definition",
                    "description": f"Added constant definition for {var_name}",
                }

            elif var_name in ["self", "cls"]:
                # Method definition issue, suggest adding to class
                return code, {
                    "success": False,
                    "reason": f"'{var_name}' reference suggests method should be in a class",
                    "suggestion": "Move this code inside a class method",
                }

            else:
                # Regular variable, try to infer type and add initialization
                if strategy in [AutoFixStrategy.MODERATE, AutoFixStrategy.AGGRESSIVE]:
                    # Analyze usage to infer type
                    inferred_type = self._infer_variable_type(code, var_name)
                    init_value = self._get_default_value_for_type(inferred_type)

                    # Add variable initialization before first use
                    lines = code.split("\n")
                    for i, line in enumerate(lines):
                        if var_name in line and not line.strip().startswith("#"):
                            lines.insert(
                                i,
                                f"    {var_name} = {init_value}  # Auto-generated initialization",
                            )
                            break

                    fixed_code = "\n".join(lines)
                    return fixed_code, {
                        "success": True,
                        "fix_type": "add_variable_initialization",
                        "description": f"Added initialization for {var_name} with inferred type {inferred_type}",
                    }

        except Exception as e:
            return code, {"success": False, "reason": f"Error parsing code: {str(e)}"}

        return code, {
            "success": False,
            "reason": "Could not automatically fix undefined variable",
        }

    async def _fix_import_error(
        self, code: str, error: ValidationError, strategy: AutoFixStrategy
    ) -> Tuple[str, Dict[str, Any]]:
        """Fix import errors."""
        # Extract module name from error
        error_message = (
            error.message if hasattr(error, "message") else error.get("message", "")
        )
        import_match = re.search(r"No module named '([^']+)'", error_message)
        if not import_match:
            return code, {"success": False, "reason": "Could not extract module name"}

        module_name = import_match.group(1)

        # Check if it's a common module with known alternatives
        common_fixes = {
            "requests": "import requests",
            "numpy": "import numpy as np",
            "pandas": "import pandas as pd",
            "matplotlib": "import matplotlib.pyplot as plt",
            "seaborn": "import seaborn as sns",
            "sklearn": "from sklearn import *",
            "fastapi": "from fastapi import FastAPI",
            "pydantic": "from pydantic import BaseModel",
        }

        if module_name in common_fixes and strategy != AutoFixStrategy.CONSERVATIVE:
            # Add the import at the top
            lines = code.split("\n")
            import_line = common_fixes[module_name]

            # Find insertion point (after existing imports)
            insert_idx = 0
            for i, line in enumerate(lines):
                if line.strip().startswith(("import ", "from ")):
                    insert_idx = i + 1
                elif line.strip() and not line.strip().startswith("#"):
                    break

            lines.insert(insert_idx, import_line)
            fixed_code = "\n".join(lines)

            return fixed_code, {
                "success": True,
                "fix_type": "add_common_import",
                "description": f"Added import for {module_name}",
                "note": f"You may need to install the package: pip install {module_name}",
            }

        return code, {
            "success": False,
            "reason": f"Unknown module {module_name}",
            "suggestion": f"Install the module with: pip install {module_name}",
        }

    async def _apply_advanced_formatting(
        self, code: str, language: str, file_path: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Apply advanced formatting beyond basic linting."""
        fixes_applied = []
        current_code = code

        if language == "python":
            # Apply docstring formatting
            current_code, docstring_fixes = await self._format_python_docstrings(
                current_code
            )
            fixes_applied.extend(docstring_fixes)

            # Apply naming convention fixes
            current_code, naming_fixes = await self._fix_python_naming_conventions(
                current_code
            )
            fixes_applied.extend(naming_fixes)

            # Apply code organization
            current_code, org_fixes = await self._organize_python_code(current_code)
            fixes_applied.extend(org_fixes)

        return current_code, fixes_applied

    async def _apply_semantic_fixes(
        self,
        code: str,
        semantic_analysis: Dict[str, Any],
        language: str,
        strategy: AutoFixStrategy,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Apply fixes based on semantic analysis."""
        fixes_applied = []
        current_code = code

        # Fix based on semantic issues
        semantic_issues = semantic_analysis.get("issues", [])

        for issue in semantic_issues:
            if issue.get("auto_fixable") and strategy != AutoFixStrategy.CONSERVATIVE:
                # Apply the suggested fix
                if "fix_code" in issue:
                    current_code = issue["fix_code"]
                    fixes_applied.append(
                        {
                            "fix_type": "semantic_fix",
                            "description": issue.get(
                                "description", "Applied semantic fix"
                            ),
                            "applied": True,
                        }
                    )

        return current_code, fixes_applied

    async def _apply_performance_optimizations(
        self, code: str, language: str, strategy: AutoFixStrategy
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Apply performance optimizations."""
        if strategy == AutoFixStrategy.CONSERVATIVE:
            return code, []

        fixes_applied = []
        current_code = code

        if language == "python":
            # List comprehension optimization
            current_code, list_comp_fixes = await self._optimize_python_list_operations(
                current_code
            )
            fixes_applied.extend(list_comp_fixes)

            # String operation optimization
            current_code, string_fixes = await self._optimize_python_string_operations(
                current_code
            )
            fixes_applied.extend(string_fixes)

        return current_code, fixes_applied

    async def _apply_security_hardening(
        self, code: str, language: str, strategy: AutoFixStrategy
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Apply security hardening fixes."""
        fixes_applied = []
        current_code = code

        if language == "python":
            # Fix SQL injection vulnerabilities
            current_code, sql_fixes = await self._fix_sql_injection_patterns(
                current_code
            )
            fixes_applied.extend(sql_fixes)

            # Fix hardcoded secrets
            current_code, secret_fixes = await self._fix_hardcoded_secrets(current_code)
            fixes_applied.extend(secret_fixes)

        return current_code, fixes_applied

    def _initialize_auto_fix_patterns(self) -> Dict[str, Any]:
        """Initialize patterns for automatic fixing."""
        return {
            "python": {
                "undefined_variable_patterns": [
                    r"name '(\w+)' is not defined",
                    r"NameError: name '(\w+)' is not defined",
                ],
                "import_error_patterns": [
                    r"No module named '([^']+)'",
                    r"ModuleNotFoundError: No module named '([^']+)'",
                ],
                "syntax_error_patterns": [r"invalid syntax", r"SyntaxError: (.+)"],
            },
            "javascript": {
                "undefined_variable_patterns": [
                    r"'(\w+)' is not defined",
                    r"ReferenceError: (\w+) is not defined",
                ]
            },
        }

    def _initialize_quality_thresholds(self) -> Dict[str, float]:
        """Initialize quality score thresholds."""
        return {"excellent": 90.0, "good": 75.0, "acceptable": 60.0, "poor": 40.0}

    def _calculate_quality_score(
        self,
        code: str,
        language: str,
        validation_result: Dict[str, Any],
        semantic_result: Dict[str, Any],
    ) -> float:
        """Calculate overall quality score."""
        base_score = 100.0  # Deduct for validation errors
        errors = validation_result.get("errors", [])
        for error in errors:
            severity = (
                error.get("severity", "low")
                if isinstance(error, dict)
                else getattr(error, "severity", "low")
            )
            if severity == "critical":
                base_score -= 20
            elif severity == "high":
                base_score -= 10
            elif severity == "medium":
                base_score -= 5
            else:
                base_score -= 2

        # Deduct for semantic issues
        semantic_issues = semantic_result.get("issues", [])
        base_score -= len(semantic_issues) * 3

        # Adjust for complexity
        complexity = semantic_result.get("complexity_score", 0)
        if complexity > 10:
            base_score -= (complexity - 10) * 2

        return max(0.0, min(100.0, base_score))

    def _calculate_complexity_metrics(
        self, code: str, language: str
    ) -> Dict[str, float]:
        """Calculate code complexity metrics."""
        if language == "python":
            try:
                tree = ast.parse(code)

                # Count various complexity factors
                num_functions = len(
                    [
                        node
                        for node in ast.walk(tree)
                        if isinstance(node, ast.FunctionDef)
                    ]
                )
                num_classes = len(
                    [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
                )
                num_if_statements = len(
                    [node for node in ast.walk(tree) if isinstance(node, ast.If)]
                )
                num_loops = len(
                    [
                        node
                        for node in ast.walk(tree)
                        if isinstance(node, (ast.For, ast.While))
                    ]
                )

                lines_of_code = len([line for line in code.split("\n") if line.strip()])

                return {
                    "cyclomatic_complexity": num_if_statements
                    + num_loops
                    + num_functions,
                    "lines_of_code": lines_of_code,
                    "num_functions": num_functions,
                    "num_classes": num_classes,
                    "complexity_per_function": (num_if_statements + num_loops)
                    / max(1, num_functions),
                }
            except Exception:
                return {"error": "Could not parse code for complexity analysis"}

        return {}

    def _calculate_maintainability_score(self, code: str, language: str) -> float:
        """Calculate maintainability score."""
        # Placeholder implementation
        lines = code.split("\n")
        non_empty_lines = [line for line in lines if line.strip()]
        comment_lines = [line for line in lines if line.strip().startswith("#")]

        comment_ratio = len(comment_lines) / max(1, len(non_empty_lines))

        # Base maintainability on comment ratio, line length, etc.
        base_score = 50.0 + (comment_ratio * 30)

        # Adjust for average line length
        avg_line_length = sum(len(line) for line in non_empty_lines) / max(
            1, len(non_empty_lines)
        )
        if avg_line_length > 80:
            base_score -= (avg_line_length - 80) * 0.5

        return max(0.0, min(100.0, base_score))

    def _calculate_reliability_score(
        self, validation_result: Dict[str, Any], semantic_result: Dict[str, Any]
    ) -> float:
        """Calculate reliability score."""
        base_score = 100.0

        # Deduct for critical issues
        critical_errors = len(
            [e for e in validation_result.get("errors", []) if e.severity == "critical"]
        )
        base_score -= critical_errors * 25

        high_errors = len(
            [e for e in validation_result.get("errors", []) if e.severity == "high"]
        )
        base_score -= high_errors * 10

        return max(0.0, min(100.0, base_score))

    # Additional helper methods for specific fixes...

    def _infer_variable_type(self, code: str, var_name: str) -> str:
        """Infer the type of a variable based on its usage."""
        # Simple heuristic-based type inference
        if f"{var_name}.append(" in code or f"{var_name}[" in code:
            return "list"
        elif f"{var_name}.get(" in code or f"{var_name}[" in code:
            return "dict"
        elif f"len({var_name})" in code:
            return "list"
        elif f"str({var_name})" in code or f'f"{var_name}"' in code:
            return "str"
        elif f"int({var_name})" in code or f"{var_name} + 1" in code:
            return "int"
        elif f"float({var_name})" in code:
            return "float"
        else:
            return "Any"

    def _get_default_value_for_type(self, type_name: str) -> str:
        """Get default value for a given type."""
        defaults = {
            "list": "[]",
            "dict": "{}",
            "str": "''",
            "int": "0",
            "float": "0.0",
            "bool": "False",
            "set": "set()",
            "tuple": "()",
            "Any": "None",
        }
        return defaults.get(type_name, "None")

    async def _format_python_docstrings(
        self, code: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Format and add missing docstrings."""
        # Placeholder for docstring formatting
        return code, []

    async def _fix_python_naming_conventions(
        self, code: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Fix Python naming convention issues."""
        # Placeholder for naming convention fixes
        return code, []

    async def _organize_python_code(
        self, code: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Organize Python code structure."""
        # Placeholder for code organization
        return code, []

    async def _optimize_python_list_operations(
        self, code: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Optimize Python list operations."""
        # Placeholder for list optimization
        return code, []

    async def _optimize_python_string_operations(
        self, code: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Optimize Python string operations."""
        # Placeholder for string optimization
        return code, []

    async def _fix_sql_injection_patterns(
        self, code: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Fix SQL injection vulnerability patterns."""
        # Placeholder for SQL injection fixes
        return code, []

    async def _fix_hardcoded_secrets(
        self, code: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Fix hardcoded secrets and credentials."""
        # Placeholder for secret fixes
        return code, []

    async def _fix_syntax_error(
        self, code: str, error: ValidationError, strategy: AutoFixStrategy
    ) -> Tuple[str, Dict[str, Any]]:
        """Fix syntax errors."""
        # Placeholder for syntax error fixes
        return code, {"success": False, "reason": "Syntax error fixing not implemented"}

    async def _fix_indentation_error(
        self, code: str, error: ValidationError, strategy: AutoFixStrategy
    ) -> Tuple[str, Dict[str, Any]]:
        """Fix indentation errors."""
        # Placeholder for indentation error fixes
        return code, {
            "success": False,
            "reason": "Indentation error fixing not implemented",
        }

    async def _fix_type_error(
        self, code: str, error: ValidationError, strategy: AutoFixStrategy
    ) -> Tuple[str, Dict[str, Any]]:
        """Fix type errors."""
        # Placeholder for type error fixes
        return code, {"success": False, "reason": "Type error fixing not implemented"}

    async def _fix_js_error(
        self, code: str, error: ValidationError, strategy: AutoFixStrategy
    ) -> Tuple[str, Dict[str, Any]]:
        """Fix JavaScript/TypeScript errors."""
        # Placeholder for JS error fixes
        return code, {
            "success": False,
            "reason": "JavaScript error fixing not implemented",
        }
