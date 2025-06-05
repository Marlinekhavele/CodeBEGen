"""
Semantic Validation Service (Tier 4)

This service implements deep semantic analysis and validation of generated code,
including AST analysis, integration testing, and architectural compliance.
"""

import ast
import asyncio
import logging
import re
import subprocess
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class AnalysisType(Enum):
    """Types of semantic analysis."""

    DATA_FLOW = "data_flow"
    CONTROL_FLOW = "control_flow"
    DEPENDENCY = "dependency"
    ARCHITECTURE = "architecture"
    PERFORMANCE = "performance"
    SECURITY = "security"


@dataclass
class SemanticIssue:
    """Represents a semantic issue found during analysis."""

    issue_type: AnalysisType
    severity: str  # critical, high, medium, low
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    function_name: Optional[str] = None
    suggestion: Optional[str] = None
    code_snippet: Optional[str] = None


class PythonASTAnalyzer:
    """Advanced AST analysis for Python code."""

    def __init__(self):
        self.issues = []
        self.variables = set()
        self.functions = {}
        self.classes = {}
        self.imports = set()

    def analyze(self, code: str, file_path: str = None) -> List[SemanticIssue]:
        """Perform comprehensive AST analysis."""
        self.issues = []
        self.variables = set()
        self.functions = {}
        self.classes = {}
        self.imports = set()

        try:
            tree = ast.parse(code)
            self.visit_node(tree)

            # Additional analysis passes
            self._analyze_data_flow(tree)
            self._analyze_control_flow(tree)
            self._analyze_complexity(tree)
            self._analyze_security_patterns(tree)

        except SyntaxError as e:
            self.issues.append(
                SemanticIssue(
                    issue_type=AnalysisType.DATA_FLOW,
                    severity="critical",
                    message=f"Syntax error: {e.msg}",
                    line_number=e.lineno,
                    suggestion="Fix syntax error before proceeding",
                )
            )
        except Exception as e:
            logger.error(f"AST analysis error: {str(e)}")

        return self.issues

    def visit_node(self, node: ast.AST):
        """Visit AST node and extract information."""
        if isinstance(node, ast.FunctionDef):
            self._analyze_function(node)
        elif isinstance(node, ast.ClassDef):
            self._analyze_class(node)
        elif isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
            self._analyze_import(node)
        elif isinstance(node, ast.Assign):
            self._analyze_assignment(node)
        elif isinstance(node, ast.Call):
            self._analyze_function_call(node)

        # Recursively visit child nodes
        for child in ast.iter_child_nodes(node):
            self.visit_node(child)

    def _analyze_function(self, node: ast.FunctionDef):
        """Analyze function definition."""
        func_name = node.name
        self.functions[func_name] = {
            "args": [arg.arg for arg in node.args.args],
            "returns": node.returns,
            "line_number": node.lineno,
            "docstring": ast.get_docstring(node),
            "decorators": [
                d.id if hasattr(d, "id") else str(d) for d in node.decorator_list
            ],
        }

        # Check for missing docstring
        if not ast.get_docstring(node):
            self.issues.append(
                SemanticIssue(
                    issue_type=AnalysisType.ARCHITECTURE,
                    severity="medium",
                    message=f"Function '{func_name}' missing docstring",
                    line_number=node.lineno,
                    function_name=func_name,
                    suggestion="Add descriptive docstring explaining function purpose and parameters",
                )
            )

        # Check function complexity (number of statements)
        stmt_count = len([n for n in ast.walk(node) if isinstance(n, ast.stmt)])
        if stmt_count > 20:
            self.issues.append(
                SemanticIssue(
                    issue_type=AnalysisType.ARCHITECTURE,
                    severity="medium",
                    message=f"Function '{func_name}' is too complex ({stmt_count} statements)",
                    line_number=node.lineno,
                    function_name=func_name,
                    suggestion="Consider breaking down into smaller functions",
                )
            )

        # Check for too many parameters
        if len(node.args.args) > 5:
            self.issues.append(
                SemanticIssue(
                    issue_type=AnalysisType.ARCHITECTURE,
                    severity="medium",
                    message=f"Function '{func_name}' has too many parameters ({len(node.args.args)})",
                    line_number=node.lineno,
                    function_name=func_name,
                    suggestion="Consider using a data class or reducing parameters",
                )
            )

    def _analyze_class(self, node: ast.ClassDef):
        """Analyze class definition."""
        class_name = node.name
        methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]

        self.classes[class_name] = {
            "methods": methods,
            "line_number": node.lineno,
            "docstring": ast.get_docstring(node),
            "bases": [
                base.id if hasattr(base, "id") else str(base) for base in node.bases
            ],
        }

        # Check for missing docstring
        if not ast.get_docstring(node):
            self.issues.append(
                SemanticIssue(
                    issue_type=AnalysisType.ARCHITECTURE,
                    severity="medium",
                    message=f"Class '{class_name}' missing docstring",
                    line_number=node.lineno,
                    suggestion="Add descriptive docstring explaining class purpose",
                )
            )

        # Check for too many methods
        if len(methods) > 15:
            self.issues.append(
                SemanticIssue(
                    issue_type=AnalysisType.ARCHITECTURE,
                    severity="medium",
                    message=f"Class '{class_name}' has too many methods ({len(methods)})",
                    line_number=node.lineno,
                    suggestion="Consider splitting into multiple classes",
                )
            )

    def _analyze_import(self, node):
        """Analyze import statements."""
        if isinstance(node, ast.Import):
            for alias in node.names:
                self.imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                self.imports.add(f"{module}.{alias.name}")

    def _analyze_assignment(self, node: ast.Assign):
        """Analyze variable assignments."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.variables.add(target.id)

    def _analyze_function_call(self, node: ast.Call):
        """Analyze function calls for potential issues."""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id

            # Check for dangerous functions
            dangerous_funcs = ["eval", "exec", "compile"]
            if func_name in dangerous_funcs:
                self.issues.append(
                    SemanticIssue(
                        issue_type=AnalysisType.SECURITY,
                        severity="critical",
                        message=f"Dangerous function call: {func_name}()",
                        line_number=node.lineno,
                        suggestion=f"Avoid using {func_name}() as it can execute arbitrary code",
                    )
                )

            # Check for SQL injection patterns
            if func_name in ["execute", "query"] and node.args:
                for arg in node.args:
                    if isinstance(arg, ast.BinOp) and isinstance(
                        arg.op, (ast.Add, ast.Mod)
                    ):
                        self.issues.append(
                            SemanticIssue(
                                issue_type=AnalysisType.SECURITY,
                                severity="high",
                                message="Potential SQL injection vulnerability",
                                line_number=node.lineno,
                                suggestion="Use parameterized queries instead of string concatenation",
                            )
                        )

    def _analyze_data_flow(self, tree: ast.AST):
        """Analyze data flow for potential issues."""
        # Track variable usage
        used_vars = set()
        defined_vars = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Store):
                    defined_vars.add(node.id)
                elif isinstance(node.ctx, ast.Load):
                    used_vars.add(node.id)

        # Check for unused variables
        unused_vars = (
            defined_vars - used_vars - {"self", "cls"}
        )  # Exclude common exceptions
        for var in unused_vars:
            if not var.startswith("_"):  # Exclude private variables
                self.issues.append(
                    SemanticIssue(
                        issue_type=AnalysisType.DATA_FLOW,
                        severity="low",
                        message=f"Unused variable: {var}",
                        suggestion="Remove unused variable or prefix with underscore if intentional",
                    )
                )

    def _analyze_control_flow(self, tree: ast.AST):
        """Analyze control flow for potential issues."""
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                # Check for nested loops
                nested_loops = [
                    n
                    for n in ast.walk(node)
                    if isinstance(n, (ast.For, ast.While)) and n != node
                ]
                if len(nested_loops) > 2:
                    self.issues.append(
                        SemanticIssue(
                            issue_type=AnalysisType.PERFORMANCE,
                            severity="medium",
                            message="Deeply nested loops detected",
                            line_number=node.lineno,
                            suggestion="Consider optimizing nested loop structure",
                        )
                    )

            elif isinstance(node, ast.If):
                # Check for long if-elif chains
                elif_count = 0
                current = node
                while hasattr(current, "orelse") and current.orelse:
                    if isinstance(current.orelse[0], ast.If):
                        elif_count += 1
                        current = current.orelse[0]
                    else:
                        break

                if elif_count > 5:
                    self.issues.append(
                        SemanticIssue(
                            issue_type=AnalysisType.ARCHITECTURE,
                            severity="medium",
                            message=f"Long if-elif chain ({elif_count} branches)",
                            line_number=node.lineno,
                            suggestion="Consider using dictionary mapping or match statement",
                        )
                    )

    def _analyze_complexity(self, tree: ast.AST):
        """Analyze code complexity."""
        # Count cyclomatic complexity
        complexity_nodes = [ast.If, ast.While, ast.For, ast.ExceptHandler, ast.With]

        for func_node in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
            complexity = 1  # Base complexity
            for node in ast.walk(func_node):
                if any(isinstance(node, t) for t in complexity_nodes):
                    complexity += 1
                elif isinstance(node, ast.BoolOp):
                    complexity += len(node.values) - 1

            if complexity > 10:
                self.issues.append(
                    SemanticIssue(
                        issue_type=AnalysisType.ARCHITECTURE,
                        severity="high",
                        message=f"High cyclomatic complexity ({complexity}) in function '{func_node.name}'",
                        line_number=func_node.lineno,
                        function_name=func_node.name,
                        suggestion="Refactor to reduce complexity and improve maintainability",
                    )
                )

    def _analyze_security_patterns(self, tree: ast.AST):
        """Analyze for security anti-patterns."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Str):
                # Check for hardcoded passwords/secrets
                value = node.s.lower()
                suspicious_patterns = ["password", "secret", "key", "token", "api_key"]
                if (
                    any(pattern in value for pattern in suspicious_patterns)
                    and len(value) > 8
                ):
                    self.issues.append(
                        SemanticIssue(
                            issue_type=AnalysisType.SECURITY,
                            severity="high",
                            message="Potential hardcoded secret detected",
                            line_number=node.lineno,
                            suggestion="Use environment variables or secure configuration for secrets",
                        )
                    )


class IntegrationTestGenerator:
    """Generates and runs integration tests for generated components."""

    def __init__(self):
        self.test_templates = {
            "endpoint": """
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_{endpoint_name}_endpoint():
    \"\"\"Test {endpoint_name} endpoint functionality.\"\"\"
    response = client.{method}("/api/{endpoint_path}")
    assert response.status_code in [200, 201, 404]  # Expected status codes

def test_{endpoint_name}_validation():
    \"\"\"Test {endpoint_name} input validation.\"\"\"
    # Test with invalid input
    response = client.{method}("/api/{endpoint_path}", json={{"invalid": "data"}})
    assert response.status_code in [400, 422]  # Validation error expected
""",
            "model": """
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.{model_name} import {model_class}
from database import Base

def test_{model_name}_creation():
    \"\"\"Test {model_class} model creation.\"\"\"
    # Create in-memory database for testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create test instance
    instance = {model_class}(**test_data)
    session.add(instance)
    session.commit()

    # Verify creation
    assert instance.id is not None
    session.close()

def test_{model_name}_validation():
    \"\"\"Test {model_class} model validation.\"\"\"
    # Test with invalid data
    with pytest.raises(ValueError):
        {model_class}(**invalid_data)
""",
        }

    async def generate_integration_tests(
        self, component_type: str, component_code: str, metadata: Dict[str, Any]
    ) -> str:
        """Generate integration tests for a component."""
        try:
            template = self.test_templates.get(component_type, "")
            if not template:
                return ""

            # Extract metadata for template substitution
            if component_type == "endpoint":
                test_code = template.format(
                    endpoint_name=metadata.get("entity_name", "test").lower(),
                    method=metadata.get("method", "get").lower(),
                    endpoint_path=metadata.get("endpoint_path", "test").strip("/"),
                )
            elif component_type == "model":
                test_code = template.format(
                    model_name=metadata.get("entity_name", "Test").lower(),
                    model_class=metadata.get("entity_name", "Test"),
                )
            else:
                test_code = template

            return test_code

        except Exception as e:
            logger.error(f"Error generating integration tests: {str(e)}")
            return ""

    async def run_integration_tests(
        self, test_code: str, project_dir: Path
    ) -> Dict[str, Any]:
        """Run integration tests and return results."""
        try:
            # Create temporary test file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(test_code)
                test_file = f.name

            # Run pytest on the test file
            result = subprocess.run(
                ["python", "-m", "pytest", test_file, "-v", "--tb=short"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "test_file": test_file,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Test execution timed out",
                "stdout": "",
                "stderr": "Test execution exceeded 30 second timeout",
            }
        except Exception as e:
            return {"success": False, "error": str(e), "stdout": "", "stderr": str(e)}


class ArchitecturalValidator:
    """Validates code against architectural patterns and SOLID principles."""

    def __init__(self):
        self.patterns = {
            "repository_pattern": {
                "description": "Repository pattern for data access",
                "indicators": ["repository", "interface", "abstract"],
                "violations": ["direct_db_access_in_controller"],
            },
            "dependency_injection": {
                "description": "Dependency injection pattern",
                "indicators": ["inject", "dependency", "container"],
                "violations": ["direct_instantiation"],
            },
            "single_responsibility": {
                "description": "Single Responsibility Principle",
                "violations": ["mixed_concerns", "god_class"],
            },
        }

    def validate_architecture(
        self, code: str, component_type: str, project_context: Optional[Dict] = None
    ) -> List[SemanticIssue]:
        """Validate architectural compliance."""
        issues = []

        try:
            # Check for SOLID principle violations
            issues.extend(self._check_solid_principles(code))

            # Check for design pattern compliance
            issues.extend(self._check_design_patterns(code, component_type))

            # Check for separation of concerns
            issues.extend(self._check_separation_of_concerns(code, component_type))

        except Exception as e:
            logger.error(f"Architectural validation error: {str(e)}")

        return issues

    def _check_solid_principles(self, code: str) -> List[SemanticIssue]:
        """Check for SOLID principle violations."""
        issues = []

        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Single Responsibility: Check if class has too many responsibilities
                    methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                    if len(methods) > 10:
                        responsibilities = self._identify_responsibilities(methods)
                        if len(responsibilities) > 3:
                            issues.append(
                                SemanticIssue(
                                    issue_type=AnalysisType.ARCHITECTURE,
                                    severity="medium",
                                    message=f"Class '{node.name}' violates Single Responsibility Principle",
                                    line_number=node.lineno,
                                    suggestion="Split class into smaller, focused classes",
                                )
                            )

                    # Open/Closed: Check for direct modification of existing code
                    # This is harder to detect statically, but we can check for patterns

                elif isinstance(node, ast.FunctionDef):
                    # Check function length (related to SRP)
                    if len(node.body) > 20:
                        issues.append(
                            SemanticIssue(
                                issue_type=AnalysisType.ARCHITECTURE,
                                severity="medium",
                                message=f"Function '{node.name}' is too long and may violate SRP",
                                line_number=node.lineno,
                                function_name=node.name,
                                suggestion="Break down into smaller, focused functions",
                            )
                        )

        except Exception as e:
            logger.error(f"SOLID validation error: {str(e)}")

        return issues

    def _identify_responsibilities(self, methods: List[ast.FunctionDef]) -> Set[str]:
        """Identify different responsibilities in a class based on method names."""
        responsibilities = set()

        patterns = {
            "data_access": ["get", "fetch", "load", "save", "update", "delete", "find"],
            "validation": ["validate", "check", "verify", "ensure"],
            "formatting": ["format", "render", "display", "show"],
            "calculation": ["calculate", "compute", "process", "transform"],
            "communication": ["send", "receive", "notify", "publish", "subscribe"],
        }

        for method in methods:
            method_name = method.name.lower()
            for responsibility, keywords in patterns.items():
                if any(keyword in method_name for keyword in keywords):
                    responsibilities.add(responsibility)
                    break

        return responsibilities

    def _check_design_patterns(
        self, code: str, component_type: str
    ) -> List[SemanticIssue]:
        """Check for proper design pattern usage."""
        issues = []

        # For now, implement basic checks
        # In a full implementation, this would be much more sophisticated

        if component_type == "model":
            # Check if model follows proper ORM pattern
            if "class" in code and "Base" not in code:
                issues.append(
                    SemanticIssue(
                        issue_type=AnalysisType.ARCHITECTURE,
                        severity="medium",
                        message="Model class should inherit from Base class",
                        suggestion="Inherit from SQLAlchemy Base or similar ORM base class",
                    )
                )

        elif component_type == "endpoint":
            # Check if endpoint follows proper controller pattern
            if "def " in code and "@app." not in code and "@router." not in code:
                issues.append(
                    SemanticIssue(
                        issue_type=AnalysisType.ARCHITECTURE,
                        severity="medium",
                        message="Endpoint function should use proper routing decorators",
                        suggestion="Add @app.get, @app.post, or similar routing decorators",
                    )
                )

        return issues

    def _check_separation_of_concerns(
        self, code: str, component_type: str
    ) -> List[SemanticIssue]:
        """Check for proper separation of concerns."""
        issues = []

        # Check for mixed concerns (e.g., business logic in controller)
        if component_type == "endpoint":
            # Look for database operations directly in controller
            db_patterns = [
                "session.query",
                "session.add",
                "session.commit",
                "SELECT",
                "INSERT",
                "UPDATE",
            ]
            if any(pattern in code for pattern in db_patterns):
                issues.append(
                    SemanticIssue(
                        issue_type=AnalysisType.ARCHITECTURE,
                        severity="medium",
                        message="Database operations found in controller",
                        suggestion="Move database operations to service layer or repository",
                    )
                )

        return issues


class SemanticValidationService:
    """
    Main service for semantic validation and deep analysis.

    This service implements Tier 4 of the quality strategy by performing
    comprehensive semantic analysis beyond syntax checking.
    """

    def __init__(self):
        self.ast_analyzer = PythonASTAnalyzer()
        self.test_generator = IntegrationTestGenerator()
        self.arch_validator = ArchitecturalValidator()

    async def perform_semantic_analysis(
        self,
        code: str,
        language: str,
        component_type: str,
        file_path: Optional[str] = None,
        project_context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive semantic analysis of code.

        Args:
            code: The code to analyze
            language: Programming language
            component_type: Type of component
            file_path: Optional file path for context
            project_context: Optional project context

        Returns:
            Comprehensive analysis results
        """
        try:
            analysis_result = {
                "semantic_issues": [],
                "architectural_issues": [],
                "integration_test": None,
                "complexity_metrics": {},
                "security_analysis": {},
                "performance_suggestions": [],
                "overall_score": 100,
                "analysis_time": 0,
            }

            start_time = (
                asyncio.get_event_loop().time()
            )  # 1. AST Analysis (currently Python only)
            if language == "python":
                semantic_issues = self.ast_analyzer.analyze(code, file_path)
                # Ensure semantic_issues is always a list
                if not isinstance(semantic_issues, list):
                    logger.warning(
                        f"semantic_issues is not a list, got {type(semantic_issues)}: {semantic_issues}"
                    )
                    semantic_issues = []

                analysis_result["semantic_issues"] = [
                    {
                        "type": (
                            issue.issue_type.value
                            if hasattr(issue.issue_type, "value")
                            else str(issue.issue_type)
                        ),
                        "severity": issue.severity,
                        "message": issue.message,
                        "line_number": issue.line_number,
                        "function_name": issue.function_name,
                        "suggestion": issue.suggestion,
                    }
                    for issue in semantic_issues
                ]  # 2. Architectural Validation
            arch_issues = self.arch_validator.validate_architecture(
                code, component_type, project_context
            )
            # Ensure arch_issues is always a list
            if not isinstance(arch_issues, list):
                logger.warning(
                    f"arch_issues is not a list, got {type(arch_issues)}: {arch_issues}"
                )
                arch_issues = []

            analysis_result["architectural_issues"] = [
                {
                    "type": (
                        issue.issue_type.value
                        if hasattr(issue.issue_type, "value")
                        else str(issue.issue_type)
                    ),
                    "severity": issue.severity,
                    "message": issue.message,
                    "line_number": issue.line_number,
                    "suggestion": issue.suggestion,
                }
                for issue in arch_issues
            ]

            # 3. Generate Integration Test
            if component_type in ["endpoint", "model"]:
                test_metadata = {
                    "entity_name": (
                        project_context.get("entity_name", "Test")
                        if project_context
                        else "Test"
                    ),
                    "method": (
                        project_context.get("method", "GET")
                        if project_context
                        else "GET"
                    ),
                    "endpoint_path": (
                        project_context.get("endpoint_path", "/test")
                        if project_context
                        else "/test"
                    ),
                }

                integration_test = await self.test_generator.generate_integration_tests(
                    component_type, code, test_metadata
                )
                analysis_result["integration_test"] = integration_test

            # 4. Calculate Complexity Metrics
            analysis_result["complexity_metrics"] = (
                await self._calculate_complexity_metrics(code, language)
            )

            # 5. Security Analysis
            analysis_result["security_analysis"] = (
                await self._perform_security_analysis(code, language)
            )

            # 6. Performance Analysis
            analysis_result["performance_suggestions"] = (
                await self._analyze_performance(code, language)
            )

            # 7. Calculate Overall Score
            analysis_result["overall_score"] = self._calculate_semantic_score(
                analysis_result
            )

            # Record analysis time
            end_time = asyncio.get_event_loop().time()
            analysis_result["analysis_time"] = end_time - start_time

            logger.info(
                f"Semantic analysis completed: {analysis_result['overall_score']} score, "
                f"{len(analysis_result['semantic_issues'])} semantic issues, "
                f"{len(analysis_result['architectural_issues'])} architectural issues"
            )

            return analysis_result

        except Exception as e:
            logger.error(f"Error in semantic analysis: {str(e)}", exc_info=True)
            return {
                "semantic_issues": [{"type": "analysis_error", "message": str(e)}],
                "architectural_issues": [],
                "integration_test": None,
                "complexity_metrics": {},
                "security_analysis": {},
                "performance_suggestions": [],
                "overall_score": 0,
                "analysis_time": 0,
            }

    async def _calculate_complexity_metrics(
        self, code: str, language: str
    ) -> Dict[str, Any]:
        """Calculate complexity metrics for the code."""
        metrics = {
            "lines_of_code": 0,
            "cyclomatic_complexity": 0,
            "cognitive_complexity": 0,
            "maintainability_index": 0,
        }

        try:
            lines = code.split("\n")
            metrics["lines_of_code"] = len(
                [
                    line
                    for line in lines
                    if line.strip() and not line.strip().startswith("#")
                ]
            )

            if language == "python":
                tree = ast.parse(code)

                # Calculate cyclomatic complexity
                complexity_nodes = [
                    ast.If,
                    ast.While,
                    ast.For,
                    ast.ExceptHandler,
                    ast.With,
                ]
                complexity = 1
                for node in ast.walk(tree):
                    if any(isinstance(node, t) for t in complexity_nodes):
                        complexity += 1
                    elif isinstance(node, ast.BoolOp):
                        complexity += len(node.values) - 1

                metrics["cyclomatic_complexity"] = complexity

                # Simple maintainability index (simplified version)
                loc = metrics["lines_of_code"]
                if loc > 0:
                    metrics["maintainability_index"] = max(
                        0,
                        171
                        - 5.2 * (complexity / loc) * 100
                        - 0.23 * complexity
                        - 16.2 * loc / 100,
                    )

        except Exception as e:
            logger.error(f"Error calculating complexity metrics: {str(e)}")

        return metrics

    async def _perform_security_analysis(
        self, code: str, language: str
    ) -> Dict[str, Any]:
        """Perform security analysis of the code."""
        security_analysis = {
            "vulnerabilities": [],
            "security_score": 100,
            "recommendations": [],
        }

        try:
            if language == "python":
                # Check for common security issues
                security_patterns = {
                    r"eval\s*\(": "Code injection vulnerability - avoid eval()",
                    r"exec\s*\(": "Code injection vulnerability - avoid exec()",
                    r"pickle\.loads\s*\(": "Deserialization vulnerability - avoid pickle.loads()",
                    r"subprocess\.call\s*\([^)]*shell\s*=\s*True": "Command injection vulnerability",
                    r"random\.random\s*\(": "Weak random number generation for security purposes",
                    r"hashlib\.md5\s*\(": "Weak hashing algorithm - use SHA-256 or better",
                }

                for pattern, message in security_patterns.items():
                    if re.search(pattern, code):
                        security_analysis["vulnerabilities"].append(
                            {
                                "type": "security_vulnerability",
                                "severity": "high",
                                "message": message,
                                "pattern": pattern,
                            }
                        )
                        security_analysis["security_score"] -= 20

                # Check for hardcoded secrets
                secret_patterns = [
                    r"password\s*=\s*['\"][^'\"]+['\"]",
                    r"secret\s*=\s*['\"][^'\"]+['\"]",
                    r"api_key\s*=\s*['\"][^'\"]+['\"]",
                    r"token\s*=\s*['\"][^'\"]+['\"]",
                ]

                for pattern in secret_patterns:
                    if re.search(pattern, code, re.IGNORECASE):
                        security_analysis["vulnerabilities"].append(
                            {
                                "type": "hardcoded_secret",
                                "severity": "critical",
                                "message": "Hardcoded secret detected",
                                "recommendation": "Use environment variables or secure configuration",
                            }
                        )
                        security_analysis["security_score"] -= 30

            # Ensure score doesn't go below 0
            security_analysis["security_score"] = max(
                0, security_analysis["security_score"]
            )

            # Generate recommendations
            if security_analysis["vulnerabilities"]:
                security_analysis["recommendations"] = [
                    "Review and fix identified security vulnerabilities",
                    "Use static analysis security testing (SAST) tools",
                    "Implement secure coding practices",
                    "Regular security code reviews",
                ]

        except Exception as e:
            logger.error(f"Error in security analysis: {str(e)}")

        return security_analysis

    async def _analyze_performance(self, code: str, language: str) -> List[str]:
        """Analyze code for performance issues and suggestions."""
        suggestions = []

        try:
            if language == "python":
                # Check for common performance anti-patterns
                performance_patterns = {
                    r"for\s+\w+\s+in\s+range\s*\(\s*len\s*\(": "Use enumerate() instead of range(len())",
                    r"\+\s*=.*\n.*\+\s*=": "Consider using list comprehension for string concatenation",
                    r"\.append\s*\(.*\)\s*\n.*\.append": "Consider using list comprehension or extend()",
                    r"try:\s*\n.*except.*:\s*\n.*pass": "Empty except block may hide performance issues",
                }

                for pattern, suggestion in performance_patterns.items():
                    if re.search(pattern, code, re.MULTILINE):
                        suggestions.append(suggestion)

                # Check for nested loops
                if re.search(r"for.*:\s*\n.*for.*:", code, re.MULTILINE):
                    suggestions.append(
                        "Consider optimizing nested loops - may have O(n²) complexity"
                    )

                # Check for database queries in loops
                if re.search(r"for.*:\s*\n.*session\.query", code, re.MULTILINE):
                    suggestions.append(
                        "Avoid database queries in loops - use batch operations"
                    )

        except Exception as e:
            logger.error(f"Error in performance analysis: {str(e)}")

        return suggestions

    def _calculate_semantic_score(self, analysis_result: Dict[str, Any]) -> int:
        """Calculate overall semantic quality score."""
        base_score = 100

        # Deduct points for issues
        semantic_issues = analysis_result.get("semantic_issues", [])
        arch_issues = analysis_result.get("architectural_issues", [])
        security_score = analysis_result.get("security_analysis", {}).get(
            "security_score", 100
        )

        # Count issues by severity
        critical_issues = len(
            [
                i
                for i in semantic_issues + arch_issues
                if i.get("severity") == "critical"
            ]
        )
        high_issues = len(
            [i for i in semantic_issues + arch_issues if i.get("severity") == "high"]
        )
        medium_issues = len(
            [i for i in semantic_issues + arch_issues if i.get("severity") == "medium"]
        )
        low_issues = len(
            [i for i in semantic_issues + arch_issues if i.get("severity") == "low"]
        )

        # Deduct points
        score = (
            base_score
            - (critical_issues * 25)
            - (high_issues * 15)
            - (medium_issues * 10)
            - (low_issues * 5)
        )

        # Factor in security score
        score = min(score, security_score)

        # Factor in complexity
        complexity_metrics = analysis_result.get("complexity_metrics", {})
        cyclomatic_complexity = complexity_metrics.get("cyclomatic_complexity", 0)
        if cyclomatic_complexity > 15:
            score -= 10
        elif cyclomatic_complexity > 10:
            score -= 5

        return max(0, min(100, score))

    async def validate_code_comprehensive(
        self,
        code: str,
        language: str,
        file_path: str,
        project_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Comprehensive code validation method that returns structured results.
        This is the method called by the quality pipeline orchestrator.

        Args:
            code: The code to validate
            language: Programming language
            file_path: Path to the file being validated
            project_dir: Optional project directory for context

        Returns:
            Dictionary with comprehensive validation results
        """
        try:
            # Use the existing perform_semantic_analysis method
            analysis_result = await self.perform_semantic_analysis(
                code=code,
                language=language,
                component_type=self._detect_component_type(file_path),
                file_path=file_path,
                project_context={"project_dir": project_dir} if project_dir else None,
            )

            # Transform to expected format for pipeline
            return {
                "patterns_analyzed": len(analysis_result.get("semantic_issues", []))
                + len(analysis_result.get("architectural_issues", [])),
                "antipatterns_detected": len(
                    [
                        issue
                        for issue in analysis_result.get("semantic_issues", [])
                        if issue.get("severity") == "error"
                    ]
                ),
                "optimization_suggestions": len(
                    analysis_result.get("performance_suggestions", [])
                ),
                "architecture_score": analysis_result.get("overall_score", 0),
                "semantic_issues": analysis_result.get("semantic_issues", []),
                "architectural_issues": analysis_result.get("architectural_issues", []),
                "complexity_metrics": analysis_result.get("complexity_metrics", {}),
                "security_analysis": analysis_result.get("security_analysis", {}),
                "integration_test": analysis_result.get("integration_test"),
                "analysis_time": analysis_result.get("analysis_time", 0),
                "success": True,
            }

        except Exception as e:
            logger.error(
                f"Error in validate_code_comprehensive: {str(e)}", exc_info=True
            )
            return {
                "patterns_analyzed": 0,
                "antipatterns_detected": 0,
                "optimization_suggestions": 0,
                "architecture_score": 0,
                "semantic_issues": [{"type": "analysis_error", "message": str(e)}],
                "architectural_issues": [],
                "complexity_metrics": {},
                "security_analysis": {},
                "integration_test": None,
                "analysis_time": 0,
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
