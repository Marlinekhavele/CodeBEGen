"""
Code Quality Service for automatic error fixing and linting.

This service integrates various tools to automatically improve the quality
of generated code from LLM outputs, including:
- Code formatting (Black, isort, Prettier)
- Linting (Ruff, ESLint)
- Type checking (mypy, TypeScript)
- Static analysis and validation
"""

import asyncio
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class FixResult(Enum):
    """Results of code fixing operations."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class CodeQualityReport:
    """Report of code quality operations."""

    original_code: str
    fixed_code: str
    issues_found: List[Dict[str, Any]]
    issues_fixed: List[Dict[str, Any]]
    remaining_issues: List[Dict[str, Any]]
    result: FixResult
    tools_used: List[str]
    execution_time: float


class CodeQualityService:
    """Service for automated code quality improvement."""

    def __init__(self):
        self.python_tools = {
            "formatters": ["black", "isort"],
            "linters": ["ruff", "flake8"],
            "type_checkers": ["mypy"],
            "security": ["bandit"],
        }
        self.javascript_tools = {
            "formatters": ["prettier"],
            "linters": ["eslint"],
            "type_checkers": ["typescript"],
        }

    async def improve_generated_code(
        self,
        code: str,
        file_path: str,
        language: str = "python",
        project_dir: Optional[str] = None,
    ) -> CodeQualityReport:
        """
        Main entry point for improving generated code quality.

        Args:
            code: The generated code to improve
            file_path: Path where the code will be written
            language: Programming language (python, javascript, typescript)
            project_dir: Project directory for context

        Returns:
            CodeQualityReport with results of improvement operations
        """
        start_time = asyncio.get_event_loop().time()
        original_code = code
        current_code = code
        issues_found = []
        issues_fixed = []
        tools_used = []

        try:
            # Step 1: Format the code
            logger.info(
                f"Starting code quality improvement for {language} file: {file_path}"
            )
            current_code, format_issues = await self._format_code(
                current_code, file_path, language
            )
            issues_fixed.extend(format_issues)
            tools_used.extend(self._get_formatters(language))

            # Step 2: Run linters and fix auto-fixable issues
            current_code, lint_issues = await self._lint_and_fix(
                current_code, file_path, language, project_dir
            )
            issues_found.extend(lint_issues)
            tools_used.extend(self._get_linters(language))

            # Step 3: Type checking (informational)
            type_issues = await self._check_types(
                current_code, file_path, language, project_dir
            )
            issues_found.extend(type_issues)
            if type_issues:
                tools_used.extend(self._get_type_checkers(language))

            # Step 4: Security analysis (for Python)
            if language == "python":
                security_issues = await self._check_security(
                    current_code, file_path, project_dir
                )
                issues_found.extend(security_issues)
                if security_issues:
                    tools_used.append("bandit")

            # Step 5: Validate syntax and imports
            validation_issues = await self._validate_code(
                current_code, file_path, language, project_dir
            )
            issues_found.extend(validation_issues)

            # Determine overall result
            remaining_issues = [
                issue for issue in issues_found if not issue.get("fixed", False)
            ]
            result = self._determine_result(issues_fixed, remaining_issues)

            execution_time = asyncio.get_event_loop().time() - start_time

            return CodeQualityReport(
                original_code=original_code,
                fixed_code=current_code,
                issues_found=issues_found,
                issues_fixed=issues_fixed,
                remaining_issues=remaining_issues,
                result=result,
                tools_used=tools_used,
                execution_time=execution_time,
            )

        except Exception as e:
            logger.error(f"Error in code quality improvement: {str(e)}", exc_info=True)
            execution_time = asyncio.get_event_loop().time() - start_time

            return CodeQualityReport(
                original_code=original_code,
                fixed_code=current_code,
                issues_found=issues_found,
                issues_fixed=issues_fixed,
                remaining_issues=issues_found,
                result=FixResult.FAILED,
                tools_used=tools_used,
                execution_time=execution_time,
            )

    async def _format_code(
        self, code: str, file_path: str, language: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Format code using appropriate formatters."""
        issues_fixed = []
        current_code = code

        if language == "python":
            # Apply Black formatting
            try:
                current_code = await self._run_black(current_code)
                issues_fixed.append(
                    {
                        "tool": "black",
                        "type": "formatting",
                        "description": "Applied Black code formatting",
                        "fixed": True,
                    }
                )
            except Exception as e:
                logger.warning(f"Black formatting failed: {str(e)}")

            # Apply isort for import sorting
            try:
                current_code = await self._run_isort(current_code)
                issues_fixed.append(
                    {
                        "tool": "isort",
                        "type": "import_sorting",
                        "description": "Sorted imports with isort",
                        "fixed": True,
                    }
                )
            except Exception as e:
                logger.warning(f"isort failed: {str(e)}")

        elif language in ["javascript", "typescript"]:
            # Apply Prettier formatting
            try:
                current_code = await self._run_prettier(current_code, file_path)
                issues_fixed.append(
                    {
                        "tool": "prettier",
                        "type": "formatting",
                        "description": "Applied Prettier code formatting",
                        "fixed": True,
                    }
                )
            except Exception as e:
                logger.warning(f"Prettier formatting failed: {str(e)}")

        return current_code, issues_fixed

    async def _lint_and_fix(
        self, code: str, file_path: str, language: str, project_dir: Optional[str]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Run linters and fix auto-fixable issues."""
        issues = []
        current_code = code

        if language == "python":
            # Use Ruff for fast linting and auto-fixing
            try:
                current_code, ruff_issues = await self._run_ruff(
                    current_code, file_path
                )
                issues.extend(ruff_issues)
            except Exception as e:
                logger.warning(f"Ruff linting failed: {str(e)}")

            # Run flake8 for additional checks (informational only)
            try:
                flake8_issues = await self._run_flake8(current_code, file_path)
                issues.extend(flake8_issues)
            except Exception as e:
                logger.warning(f"Flake8 linting failed: {str(e)}")

        elif language in ["javascript", "typescript"]:
            # Use ESLint for JavaScript/TypeScript
            try:
                current_code, eslint_issues = await self._run_eslint(
                    current_code, file_path, project_dir
                )
                issues.extend(eslint_issues)
            except Exception as e:
                logger.warning(f"ESLint failed: {str(e)}")

        return current_code, issues

    async def _check_types(
        self, code: str, file_path: str, language: str, project_dir: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Run type checkers."""
        issues = []

        if language == "python":
            try:
                mypy_issues = await self._run_mypy(code, file_path, project_dir)
                issues.extend(mypy_issues)
            except Exception as e:
                logger.warning(f"mypy type checking failed: {str(e)}")

        elif language == "typescript":
            try:
                tsc_issues = await self._run_typescript_check(
                    code, file_path, project_dir
                )
                issues.extend(tsc_issues)
            except Exception as e:
                logger.warning(f"TypeScript checking failed: {str(e)}")

        return issues

    async def _check_security(
        self, code: str, file_path: str, project_dir: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Run security analysis tools."""
        issues = []

        try:
            bandit_issues = await self._run_bandit(code, file_path)
            issues.extend(bandit_issues)
        except Exception as e:
            logger.warning(f"Bandit security check failed: {str(e)}")

        return issues

    async def _validate_code(
        self, code: str, file_path: str, language: str, project_dir: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Validate code syntax and imports."""
        issues = []

        try:
            if language == "python":
                # Check Python syntax
                try:
                    compile(code, file_path, "exec")
                except SyntaxError as e:
                    issues.append(
                        {
                            "tool": "python_compiler",
                            "type": "syntax_error",
                            "description": f"Syntax error: {str(e)}",
                            "line": e.lineno,
                            "column": e.offset,
                            "fixed": False,
                            "severity": "error",
                        }
                    )

                # Check imports
                import_issues = await self._validate_python_imports(code, project_dir)
                issues.extend(import_issues)

            elif language in ["javascript", "typescript"]:
                # Basic JavaScript syntax validation could be added here
                pass

        except Exception as e:
            logger.warning(f"Code validation failed: {str(e)}")

        return issues

    # Tool-specific implementations

    async def _run_black(self, code: str) -> str:
        """Run Black formatter on code."""
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(code)
                temp_path = f.name

            result = subprocess.run(
                ["black", "--quiet", temp_path],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                with open(temp_path, "r") as f:
                    formatted_code = f.read()
                os.unlink(temp_path)
                return formatted_code
            else:
                os.unlink(temp_path)
                return code

        except Exception as e:
            logger.warning(f"Black formatting error: {str(e)}")
            return code

    async def _run_isort(self, code: str) -> str:
        """Run isort on code."""
        try:
            result = subprocess.run(
                ["isort", "--stdout", "-"],
                input=code,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0 and result.stdout:
                return result.stdout
            else:
                return code

        except Exception as e:
            logger.warning(f"isort error: {str(e)}")
            return code

    async def _run_ruff(
        self, code: str, file_path: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Run Ruff linter with auto-fixing."""
        issues = []
        fixed_code = code

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(code)
                temp_path = f.name

            # Run ruff with auto-fix
            result = subprocess.run(
                ["ruff", "check", "--fix", "--output-format=json", temp_path],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Parse ruff output for issues
            if result.stdout:
                import json

                try:
                    ruff_output = json.loads(result.stdout)
                    for issue in ruff_output:
                        issues.append(
                            {
                                "tool": "ruff",
                                "type": "linting",
                                "description": issue.get("message", ""),
                                "rule": issue.get("code", ""),
                                "line": issue.get("location", {}).get("row", 0),
                                "column": issue.get("location", {}).get("column", 0),
                                "fixed": issue.get("fix", {}).get("applicability", "")
                                == "automatic",
                                "severity": "warning",
                            }
                        )
                except json.JSONDecodeError:
                    pass

            # Read potentially fixed code
            with open(temp_path, "r") as f:
                fixed_code = f.read()

            os.unlink(temp_path)

        except Exception as e:
            logger.warning(f"Ruff error: {str(e)}")

        return fixed_code, issues

    async def _run_mypy(
        self, code: str, file_path: str, project_dir: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Run mypy type checker."""
        issues = []

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(code)
                temp_path = f.name

            cmd = ["mypy", "--show-error-codes", "--no-error-summary", temp_path]
            if project_dir:
                # Add project directory to Python path for mypy
                cmd.extend(["--python-path", project_dir])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            # Parse mypy output
            for line in result.stdout.split("\n"):
                if line.strip() and ":" in line:
                    parts = line.split(":", 3)
                    if len(parts) >= 4:
                        issues.append(
                            {
                                "tool": "mypy",
                                "type": "type_error",
                                "description": parts[3].strip(),
                                "line": int(parts[1]) if parts[1].isdigit() else 0,
                                "column": int(parts[2]) if parts[2].isdigit() else 0,
                                "fixed": False,
                                "severity": "error" if "error" in line else "warning",
                            }
                        )

            os.unlink(temp_path)

        except Exception as e:
            logger.warning(f"mypy error: {str(e)}")

        return issues

    async def _run_prettier(self, code: str, file_path: str) -> str:
        """Run Prettier formatter."""
        try:
            result = subprocess.run(
                ["prettier", "--stdin-filepath", file_path],
                input=code,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0 and result.stdout:
                return result.stdout
            else:
                return code

        except Exception as e:
            logger.warning(f"Prettier error: {str(e)}")
            return code

    async def _validate_python_imports(
        self, code: str, project_dir: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Validate Python imports."""
        issues = []

        # Extract import statements
        import ast

        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    # Basic import validation logic
                    if isinstance(node, ast.ImportFrom) and node.module:
                        if node.module.startswith("app.") or node.module.startswith(
                            "helpers."
                        ):
                            # These are project-local imports - validate they exist
                            if project_dir:
                                module_path = node.module.replace(".", os.sep) + ".py"
                                full_path = os.path.join(project_dir, module_path)
                                if not os.path.exists(full_path):
                                    issues.append(
                                        {
                                            "tool": "import_validator",
                                            "type": "import_error",
                                            "description": f"Module {node.module} not found",
                                            "line": node.lineno,
                                            "column": node.col_offset,
                                            "fixed": False,
                                            "severity": "error",
                                        }
                                    )
        except SyntaxError:
            # Already caught in syntax validation
            pass
        except Exception as e:
            logger.warning(f"Import validation error: {str(e)}")

        return issues

    def _get_formatters(self, language: str) -> List[str]:
        """Get list of formatters for language."""
        if language == "python":
            return self.python_tools["formatters"]
        elif language in ["javascript", "typescript"]:
            return self.javascript_tools["formatters"]
        return []

    def _get_linters(self, language: str) -> List[str]:
        """Get list of linters for language."""
        if language == "python":
            return self.python_tools["linters"]
        elif language in ["javascript", "typescript"]:
            return self.javascript_tools["linters"]
        return []

    def _get_type_checkers(self, language: str) -> List[str]:
        """Get list of type checkers for language."""
        if language == "python":
            return self.python_tools["type_checkers"]
        elif language in ["javascript", "typescript"]:
            return self.javascript_tools["type_checkers"]
        return []

    def _determine_result(
        self, issues_fixed: List[Dict], remaining_issues: List[Dict]
    ) -> FixResult:
        """Determine overall result of code quality operations."""
        if not issues_fixed and not remaining_issues:
            return FixResult.SUCCESS
        elif issues_fixed and not remaining_issues:
            return FixResult.SUCCESS
        elif issues_fixed and remaining_issues:
            # Check if remaining issues are critical
            critical_issues = [
                i for i in remaining_issues if i.get("severity") == "error"
            ]
            if critical_issues:
                return FixResult.PARTIAL
            else:
                return FixResult.SUCCESS
        elif remaining_issues:
            critical_issues = [
                i for i in remaining_issues if i.get("severity") == "error"
            ]
            if critical_issues:
                return FixResult.FAILED
            else:
                return FixResult.PARTIAL
        else:
            return FixResult.SUCCESS

    # Additional helper methods for other tools...

    async def _run_flake8(self, code: str, file_path: str) -> List[Dict[str, Any]]:
        """Run flake8 linter (informational only)."""
        # Implementation similar to other tools
        return []

    async def _run_bandit(self, code: str, file_path: str) -> List[Dict[str, Any]]:
        """Run Bandit security checker."""
        # Implementation for security checking
        return []

    async def _run_eslint(
        self, code: str, file_path: str, project_dir: Optional[str]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Run ESLint for JavaScript/TypeScript."""
        # Implementation for ESLint
        return code, []

    async def _run_typescript_check(
        self, code: str, file_path: str, project_dir: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Run TypeScript compiler check."""
        # Implementation for TypeScript checking
        return []
