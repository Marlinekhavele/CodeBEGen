"""
Quality Assurance Pipeline Orchestrator

This service orchestrates the complete 4-tier quality assurance pipeline:
- Tier 1: LLM Prompt Enhancement (Prevention-First)
- Tier 2: Real-time Validation (During Generation)
- Tier 3: Automated Code Quality (Auto-fixing)
- Tier 4: Semantic Validation (Deep Analysis)
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from .enhanced_code_quality_service import AutoFixStrategy, EnhancedCodeQualityService
from .prompt_enhancement_service import PromptEnhancementService
from .quality_metrics_collector import QualityMetricsCollector
from .real_time_validation_service import RealTimeValidationService
from .semantic_validation_service import SemanticValidationService

logger = logging.getLogger(__name__)


class QualityLevel(Enum):
    """Quality assurance levels."""

    BASIC = "basic"  # Tier 1 + 2 only
    STANDARD = "standard"  # Tier 1 + 2 + 3
    COMPREHENSIVE = "comprehensive"  # All 4 tiers
    CUSTOM = "custom"  # Custom tier selection


class PipelineMode(Enum):
    """Pipeline execution modes."""

    SEQUENTIAL = "sequential"  # Run tiers one after another
    PARALLEL = "parallel"  # Run compatible tiers in parallel
    STREAMING = "streaming"  # Stream results as they become available


@dataclass
class QualityPipelineConfig:
    """Configuration for the quality pipeline."""

    quality_level: QualityLevel = QualityLevel.STANDARD
    pipeline_mode: PipelineMode = PipelineMode.SEQUENTIAL
    auto_fix_strategy: AutoFixStrategy = AutoFixStrategy.MODERATE

    # Tier enablement
    enable_tier1: bool = True  # Prompt Enhancement
    enable_tier2: bool = True  # Real-time Validation
    enable_tier3: bool = True  # Code Quality
    enable_tier4: bool = False  # Semantic Validation (expensive)

    # Performance settings
    max_execution_time: float = 30.0  # seconds
    enable_caching: bool = True
    parallel_processing: bool = False

    # Quality thresholds
    min_quality_score: float = 70.0
    max_iterations: int = 3

    # Context settings
    include_project_context: bool = True
    include_historical_patterns: bool = True


@dataclass
class PipelineResult:
    """Result of the complete quality pipeline."""

    # Input
    original_prompt: str
    original_code: str

    # Enhanced inputs
    enhanced_prompt: str

    # Final outputs
    final_code: str
    quality_score: float

    # Tier results
    tier1_result: Optional[Dict[str, Any]] = None  # Prompt enhancement
    tier2_result: Optional[Dict[str, Any]] = None  # Real-time validation
    tier3_result: Optional[Dict[str, Any]] = None  # Code quality
    tier4_result: Optional[Dict[str, Any]] = None  # Semantic validation

    # Pipeline metrics
    total_execution_time: float = 0.0
    iterations_performed: int = 0
    tier_execution_times: Dict[str, float] = None

    # Quality metrics
    issues_prevented: List[Dict[str, Any]] = None
    issues_detected: List[Dict[str, Any]] = None
    issues_fixed: List[Dict[str, Any]] = None
    remaining_issues: List[Dict[str, Any]] = None

    # Recommendations
    improvement_suggestions: List[Dict[str, Any]] = None
    next_iteration_recommendations: List[Dict[str, Any]] = None


class QualityAssurancePipeline:
    """Main orchestrator for the 4-tier quality assurance pipeline."""

    def __init__(self, config: Optional[QualityPipelineConfig] = None):
        self.config = config or QualityPipelineConfig()

        # Initialize tier services (add aliases for compatibility)
        self.tier1_service = (
            PromptEnhancementService() if self.config.enable_tier1 else None
        )
        self.tier2_service = (
            RealTimeValidationService() if self.config.enable_tier2 else None
        )
        self.tier3_service = (
            EnhancedCodeQualityService() if self.config.enable_tier3 else None
        )
        self.tier4_service = (
            SemanticValidationService() if self.config.enable_tier4 else None
        )

        # Add aliases for compatibility with tests
        self.prompt_service = self.tier1_service
        self.validation_service = self.tier2_service
        self.quality_service = self.tier3_service
        self.semantic_service = self.tier4_service

        # Initialize metrics collector
        self.metrics_collector = QualityMetricsCollector()

        # Pipeline state
        self.execution_cache = {}

    async def process_code_generation(
        self,
        prompt: str,
        code: str,
        file_path: str,
        language: str = "python",
        project_dir: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> PipelineResult:
        """
        Process code through the complete quality assurance pipeline.

        Args:
            prompt: Original prompt for code generation
            code: Generated code to process
            file_path: Target file path
            language: Programming language
            project_dir: Project directory for context
            context: Additional context information

        Returns:
            PipelineResult with comprehensive quality analysis and improved code
        """
        start_time = time.time()
        tier_times = {}

        try:
            logger.info(
                f"Starting quality pipeline for {file_path} (level: {self.config.quality_level.value})"
            )

            # Initialize result
            result = PipelineResult(
                original_prompt=prompt,
                original_code=code,
                enhanced_prompt=prompt,
                final_code=code,
                quality_score=0.0,
                tier_execution_times=tier_times,
                issues_prevented=[],
                issues_detected=[],
                issues_fixed=[],
                remaining_issues=[],
                improvement_suggestions=[],
                next_iteration_recommendations=[],
            )

            # Phase 1: Pre-generation Enhancement (Tier 1)
            if self.tier1_service:
                tier1_start = time.time()
                result.tier1_result = await self._execute_tier1(
                    prompt, language, project_dir, context
                )
                result.enhanced_prompt = result.tier1_result.get(
                    "enhanced_prompt", prompt
                )
                tier_times["tier1"] = time.time() - tier1_start
                logger.info(f"Tier 1 completed in {tier_times['tier1']:.2f}s")

            # Phase 2: Real-time Validation (Tier 2)
            if self.tier2_service:
                tier2_start = time.time()
                result.tier2_result = await self._execute_tier2(
                    result.final_code, language, file_path, context
                )
                tier_times["tier2"] = time.time() - tier2_start
                logger.info(f"Tier 2 completed in {tier_times['tier2']:.2f}s")

            # Phase 3: Iterative Quality Improvement
            iteration = 0
            current_code = result.final_code

            while iteration < self.config.max_iterations:
                iteration += 1
                logger.info(f"Starting quality improvement iteration {iteration}")

                # Tier 3: Enhanced Code Quality
                if self.tier3_service:
                    tier3_start = time.time()
                    tier3_result = await self._execute_tier3(
                        current_code, file_path, language, project_dir, context
                    )

                    if iteration == 1:
                        result.tier3_result = tier3_result
                        tier_times["tier3"] = time.time() - tier3_start

                    current_code = tier3_result.get("fixed_code", current_code)
                    current_quality = tier3_result.get("quality_score", 0.0)

                    # Check if quality threshold is met
                    if current_quality >= self.config.min_quality_score:
                        logger.info(f"Quality threshold met: {current_quality:.1f}%")
                        break

                # Tier 4: Semantic Validation (if enabled)
                if self.tier4_service and iteration == 1:  # Only run once due to cost
                    tier4_start = time.time()
                    result.tier4_result = await self._execute_tier4(
                        current_code, language, file_path, project_dir, context
                    )
                    tier_times["tier4"] = time.time() - tier4_start
                    logger.info(f"Tier 4 completed in {tier_times['tier4']:.2f}s")

                # Check execution time limit
                if time.time() - start_time > self.config.max_execution_time:
                    logger.warning("Pipeline execution time limit reached")
                    break

            # Finalize results
            result.final_code = current_code
            result.iterations_performed = iteration
            result.total_execution_time = time.time() - start_time

            # Calculate final quality score
            result.quality_score = await self._calculate_final_quality_score(result)

            # Compile issues and recommendations
            await self._compile_pipeline_insights(result)

            logger.info(
                f"Pipeline completed: {result.quality_score:.1f}% quality in {result.total_execution_time:.2f}s"
            )

            return result

        except Exception as e:
            logger.error(f"Pipeline execution failed: {str(e)}", exc_info=True)
            # Return partial result
            result.total_execution_time = time.time() - start_time
            result.remaining_issues.append(
                {"severity": "critical", "type": "pipeline_error", "message": str(e)}
            )

            return result

    async def run_pipeline(
        self,
        code: str,
        language: str = "python",
        file_path: str = "temp.py",
        quality_level: Optional[QualityLevel] = None,
        prompt: str = "",
        project_dir: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> PipelineResult:
        """
        Alias for process_code_generation method to maintain compatibility.

        Args:
            code: Generated code to process
            language: Programming language
            file_path: Target file path
            quality_level: Quality level override
            prompt: Original prompt for code generation
            project_dir: Project directory for context
            context: Additional context information

        Returns:
            PipelineResult with comprehensive quality analysis and improved code"""  # Update config if quality level is provided
        if quality_level:
            original_level = self.config.quality_level
            self.config.quality_level = quality_level

        start_time = time.time()
        try:
            pipeline_result = await self.process_code_generation(
                prompt=prompt or "Generated code quality improvement",
                code=code,
                file_path=file_path,
                language=language,
                project_dir=project_dir,
                context=context,
            )

            # Collect metrics
            execution_stats = self._calculate_execution_stats(
                code, pipeline_result, start_time
            )
            project_id = context.get("project_id", "unknown") if context else "unknown"

            # Collect metrics for analysis
            self.metrics_collector.collect_metrics(
                project_id=project_id,
                language=language,
                quality_level=self.config.quality_level.value,
                pipeline_result=self._convert_pipeline_result_to_dict(pipeline_result),
                execution_stats=execution_stats,
            )
            # Convert PipelineResult to dictionary for backward compatibility
            result_dict = {
                "tier1_result": pipeline_result.tier1_result,
                "tier2_result": pipeline_result.tier2_result,
                "tier3_result": pipeline_result.tier3_result,
                "tier4_result": pipeline_result.tier4_result,
                "pipeline_summary": {
                    "total_issues_found": len(pipeline_result.issues_detected),
                    "total_issues_fixed": len(pipeline_result.issues_fixed),
                    "overall_quality_score": pipeline_result.quality_score,
                    "quality_score": pipeline_result.quality_score,
                    "processing_time_ms": pipeline_result.total_execution_time * 1000,
                    "execution_time": pipeline_result.total_execution_time,
                    "quality_improvement_percentage": max(
                        0, pipeline_result.quality_score - 50
                    ),  # Assuming base quality of 50
                    "final_code": pipeline_result.final_code,
                },
                "original_code": pipeline_result.original_code,
                "final_code": pipeline_result.final_code,
                "quality_score": pipeline_result.quality_score,
                "issues_detected": pipeline_result.issues_detected,
                "issues_fixed": pipeline_result.issues_fixed,
                "improvement_suggestions": pipeline_result.improvement_suggestions,
                "success": True,
                "execution_stats": execution_stats,
            }

            return result_dict

        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            # Return error result for compatibility
            return {
                "success": False,
                "error": str(e),
                "original_code": code,
                "final_code": code,
                "quality_score": 0,
                "issues_detected": [],
                "issues_fixed": [],
                "improvement_suggestions": [],
            }
        finally:
            # Restore original config
            if quality_level:
                self.config.quality_level = original_level

    def run_pipeline_sync(
        self,
        code: str,
        language: str = "python",
        file_path: str = "temp.py",
        quality_level: Optional[QualityLevel] = None,
        prompt: str = "",
        project_dir: Optional[str] = None,
        project_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Synchronous wrapper for run_pipeline method.

        Args:
            code: Generated code to process
            language: Programming language
            file_path: Target file path
            quality_level: Quality level override
            prompt: Original prompt for code generation
            project_dir: Project directory for context
            project_id: Project ID for metrics (legacy parameter)
            context: Additional context information

        Returns:
            Dictionary with pipeline results
        """
        # Handle legacy project_id parameter
        if project_id and not context:
            context = {"project_id": project_id}
        elif project_id and context and "project_id" not in context:
            context["project_id"] = project_id

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.run_pipeline(
                code=code,
                language=language,
                file_path=file_path,
                quality_level=quality_level,
                prompt=prompt,
                project_dir=project_dir,
                context=context,
            )
        )

    async def _execute_tier1(
        self,
        prompt: str,
        language: str,
        project_dir: Optional[str],
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute Tier 1: Prompt Enhancement."""
        try:
            enhanced_prompt = await self.tier1_service.enhance_prompt(
                original_prompt=prompt,
                language=language,
                project_dir=project_dir,
                context=context or {},
            )
            return {
                "enhanced_prompt": enhanced_prompt.enhanced_prompt,
                "enhancements_applied": enhanced_prompt.enhancements_applied,
                "context_injected": enhanced_prompt.context_injected,
                "error_prevention_added": bool(
                    enhanced_prompt.error_prevention_guidelines
                ),
                "success": True,
            }

        except Exception as e:
            logger.error(f"Tier 1 execution failed: {str(e)}")
            return {"enhanced_prompt": prompt, "success": False, "error": str(e)}

    async def _execute_tier2(
        self,
        code: str,
        language: str,
        file_path: str,
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute Tier 2: Real-time Validation."""
        try:
            validation_result = await self.tier2_service.validate_code_streaming(
                code=code, language=language, file_path=file_path
            )

            return {
                "validation_errors": validation_result.get("errors", []),
                "syntax_valid": validation_result.get("syntax_valid", True),
                "constraint_violations": validation_result.get(
                    "constraint_violations", []
                ),
                "suggestions": validation_result.get("suggestions", []),
                "success": True,
            }

        except Exception as e:
            logger.error(f"Tier 2 execution failed: {str(e)}")
            return {
                "validation_errors": [
                    {"severity": "high", "message": f"Validation failed: {str(e)}"}
                ],
                "success": False,
                "error": str(e),
            }

    async def _execute_tier3(
        self,
        code: str,
        file_path: str,
        language: str,
        project_dir: Optional[str],
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute Tier 3: Enhanced Code Quality."""
        try:
            quality_result = await self.tier3_service.enhance_code_quality(
                code=code,
                file_path=file_path,
                language=language,
                project_dir=project_dir,
                fix_strategy=self.config.auto_fix_strategy,
                context=context,
            )

            return {
                "fixed_code": quality_result.fixed_code,
                "quality_score": quality_result.quality_score,
                "issues_found": quality_result.issues_found,
                "issues_fixed": quality_result.issues_fixed,
                "auto_fixes_applied": quality_result.auto_fixes_applied,
                "complexity_metrics": quality_result.complexity_metrics,
                "maintainability_score": quality_result.maintainability_score,
                "success": True,
            }

        except Exception as e:
            logger.error(f"Tier 3 execution failed: {str(e)}")
            return {
                "fixed_code": code,
                "quality_score": 0.0,
                "success": False,
                "error": str(e),
            }

    async def _execute_tier4(
        self,
        code: str,
        language: str,
        file_path: str,
        project_dir: Optional[str],
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute Tier 4: Semantic Validation."""
        try:
            semantic_result = await self.tier4_service.validate_code_comprehensive(
                code=code,
                language=language,
                file_path=file_path,
                project_dir=project_dir,
            )

            return {
                "semantic_issues": semantic_result.get("issues", []),
                "security_analysis": semantic_result.get("security_analysis", {}),
                "performance_analysis": semantic_result.get("performance_analysis", {}),
                "architectural_compliance": semantic_result.get(
                    "architectural_compliance", {}
                ),
                "integration_tests": semantic_result.get("integration_tests", []),
                "complexity_analysis": semantic_result.get("complexity_analysis", {}),
                "success": True,
            }

        except Exception as e:
            logger.error(f"Tier 4 execution failed: {str(e)}")
            return {
                "semantic_issues": [
                    {
                        "severity": "medium",
                        "message": f"Semantic analysis failed: {str(e)}",
                    }
                ],
                "success": False,
                "error": str(e),
            }

    async def _calculate_final_quality_score(self, result: PipelineResult) -> float:
        """Calculate the final quality score based on all tier results."""
        base_score = 100.0

        # Deduct for remaining issues
        for issue in result.remaining_issues:
            severity = issue.get("severity", "low")
            if severity == "critical":
                base_score -= 25
            elif severity == "high":
                base_score -= 15
            elif severity == "medium":
                base_score -= 10
            else:
                base_score -= 5

        # Bonus for fixes applied
        bonus = min(20, len(result.issues_fixed) * 2)
        base_score += bonus

        # Consider tier-specific scores
        if result.tier3_result and "quality_score" in result.tier3_result:
            tier3_score = result.tier3_result["quality_score"]
            base_score = (base_score + tier3_score) / 2

        return max(0.0, min(100.0, base_score))

    async def _compile_pipeline_insights(self, result: PipelineResult) -> None:
        """Compile insights and recommendations from all tiers."""
        # Collect all issues
        all_issues = []

        if result.tier2_result:
            all_issues.extend(result.tier2_result.get("validation_errors", []))

        if result.tier3_result:
            all_issues.extend(result.tier3_result.get("issues_found", []))

        if result.tier4_result:
            all_issues.extend(result.tier4_result.get("semantic_issues", []))

        # Categorize issues
        result.issues_detected = [
            issue for issue in all_issues if not issue.get("fixed", False)
        ]
        result.remaining_issues = [
            issue for issue in all_issues if not issue.get("fixed", False)
        ]

        # Collect fixes
        if result.tier3_result:
            result.issues_fixed = result.tier3_result.get("issues_fixed", [])

        # Generate improvement suggestions
        result.improvement_suggestions = await self._generate_improvement_suggestions(
            result
        )

        # Generate next iteration recommendations
        if result.quality_score < self.config.min_quality_score:
            result.next_iteration_recommendations = (
                await self._generate_iteration_recommendations(result)
            )

    async def _generate_improvement_suggestions(
        self, result: PipelineResult
    ) -> List[Dict[str, Any]]:
        """Generate suggestions for code improvement."""
        suggestions = []

        # Analyze remaining issues
        critical_issues = [
            issue
            for issue in result.remaining_issues
            if issue.get("severity") == "critical"
        ]
        if critical_issues:
            suggestions.append(
                {
                    "type": "critical_fix",
                    "priority": "high",
                    "description": f"Address {len(critical_issues)} critical issues to improve code reliability",
                    "actions": [
                        "Fix syntax errors",
                        "Resolve undefined variables",
                        "Handle exceptions properly",
                    ],
                }
            )

        # Check complexity
        if result.tier3_result and "complexity_metrics" in result.tier3_result:
            complexity = result.tier3_result["complexity_metrics"]
            if complexity.get("cyclomatic_complexity", 0) > 10:
                suggestions.append(
                    {
                        "type": "complexity_reduction",
                        "priority": "medium",
                        "description": "Consider breaking down complex functions for better maintainability",
                        "actions": [
                            "Extract helper functions",
                            "Simplify conditional logic",
                            "Reduce nesting levels",
                        ],
                    }
                )

        # Check maintainability
        if (
            result.tier3_result
            and result.tier3_result.get("maintainability_score", 100) < 70
        ):
            suggestions.append(
                {
                    "type": "maintainability",
                    "priority": "medium",
                    "description": "Improve code maintainability with better documentation and structure",
                    "actions": [
                        "Add docstrings",
                        "Improve variable names",
                        "Add type hints",
                    ],
                }
            )

        return suggestions

    async def _generate_iteration_recommendations(
        self, result: PipelineResult
    ) -> List[Dict[str, Any]]:
        """Generate recommendations for next pipeline iteration."""
        recommendations = []

        if result.quality_score < 50:
            recommendations.append(
                {
                    "action": "increase_fix_strategy",
                    "description": "Use more aggressive auto-fixing strategy",
                    "details": "Switch to AGGRESSIVE mode for more comprehensive fixes",
                }
            )

        if not self.config.enable_tier4 and result.quality_score < 80:
            recommendations.append(
                {
                    "action": "enable_semantic_validation",
                    "description": "Enable Tier 4 semantic validation for deeper analysis",
                    "details": "Semantic validation can catch architectural and design issues",
                }
            )

        if len(result.remaining_issues) > 10:
            recommendations.append(
                {
                    "action": "focus_critical_issues",
                    "description": "Focus on critical and high-severity issues first",
                    "details": "Address the most impactful issues before minor improvements",
                }
            )

        return recommendations

    async def validate_pipeline_config(
        self, config: QualityPipelineConfig
    ) -> Dict[str, Any]:
        """Validate pipeline configuration."""
        validation_result = {"valid": True, "warnings": [], "errors": []}

        # Check tier dependencies
        if config.enable_tier3 and not config.enable_tier2:
            validation_result["warnings"].append(
                "Tier 3 is most effective with Tier 2 real-time validation enabled"
            )

        # Check performance settings
        if config.max_execution_time < 5.0:
            validation_result["warnings"].append(
                "Very short execution time limit may prevent effective quality improvement"
            )

        if config.enable_tier4 and config.max_execution_time < 15.0:
            validation_result["warnings"].append(
                "Tier 4 semantic validation requires more execution time"
            )

        # Check quality thresholds
        if config.min_quality_score > 95.0:
            validation_result["warnings"].append(
                "Very high quality threshold may be difficult to achieve consistently"
            )

        return validation_result

    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get current pipeline status and statistics."""
        return {
            "config": {
                "quality_level": self.config.quality_level.value,
                "enabled_tiers": {
                    "tier1": self.config.enable_tier1,
                    "tier2": self.config.enable_tier2,
                    "tier3": self.config.enable_tier3,
                    "tier4": self.config.enable_tier4,
                },
                "auto_fix_strategy": self.config.auto_fix_strategy.value,
                "min_quality_score": self.config.min_quality_score,
            },
            "services_initialized": {
                "tier1": self.tier1_service is not None,
                "tier2": self.tier2_service is not None,
                "tier3": self.tier3_service is not None,
                "tier4": self.tier4_service is not None,
            },
            "cache_size": len(self.execution_cache),
        }

    def _calculate_execution_stats(
        self, code: str, pipeline_result: "PipelineResult", start_time: float
    ) -> Dict[str, Any]:
        """Calculate execution statistics for metrics collection."""
        execution_time = time.time() - start_time

        return {
            "execution_time": execution_time,
            "code_lines": len(code.splitlines()) if code else 0,
            "issues_found": (
                len(pipeline_result.issues_detected)
                if hasattr(pipeline_result, "issues_detected")
                else 0
            ),
            "issues_fixed": (
                len(pipeline_result.issues_fixed)
                if hasattr(pipeline_result, "issues_fixed")
                else 0
            ),
            "quality_score": getattr(pipeline_result, "quality_score", 0),
            "tier1_time": getattr(pipeline_result, "tier1_execution_time", 0),
            "tier2_time": getattr(pipeline_result, "tier2_execution_time", 0),
            "tier3_time": getattr(pipeline_result, "tier3_execution_time", 0),
            "tier4_time": getattr(pipeline_result, "tier4_execution_time", 0),
            "memory_usage": self._get_memory_usage(),
            "success": getattr(pipeline_result, "success", True),
        }

    def _convert_pipeline_result_to_dict(
        self, pipeline_result: "PipelineResult"
    ) -> Dict[str, Any]:
        """Convert PipelineResult object to dictionary for metrics collection."""
        if hasattr(pipeline_result, "__dict__"):
            result_dict = pipeline_result.__dict__.copy()
        else:
            # Fallback for dictionary-like results
            result_dict = dict(pipeline_result) if pipeline_result else {}

        # Ensure all required fields are present
        required_fields = {
            "quality_score": 0,
            "issues_detected": [],
            "issues_fixed": [],
            "final_code": "",
            "success": True,
            "total_execution_time": 0,
        }

        for field, default_value in required_fields.items():
            if field not in result_dict:
                result_dict[field] = default_value

        return result_dict

    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil

            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # Convert to MB
        except ImportError:
            logger.warning("psutil not available, memory usage not tracked")
            return 0.0
        except Exception as e:
            logger.warning(f"Failed to get memory usage: {e}")
            return 0.0

    async def analyze_error_for_file_identification(
        self,
        error_message: str,
        traceback_text: str,
        project_dir: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze error messages and tracebacks to identify which files need fixing.

        This method uses advanced heuristics to determine the actual source of errors,
        particularly useful when the frontend doesn't have complete traceback information.

        Args:
            error_message: The error message
            traceback_text: Full traceback if available
            project_dir: Project directory for file analysis
            context: Additional context about the error

        Returns:
            Dict containing identified file, confidence level, and suggested fixes
        """
        try:
            result = {
                "identified_file": None,
                "confidence": 0.0,
                "error_type": "unknown",
                "suggested_fixes": [],
                "analysis_details": {},
            }

            # Import error patterns
            import_patterns = {
                "ForeignKey": {
                    "files": ["models/*.py"],
                    "import_fix": "from sqlalchemy import ForeignKey",
                },
                "relationship": {
                    "files": ["models/*.py"],
                    "import_fix": "from sqlalchemy.orm import relationship",
                },
                "BaseModel": {
                    "files": ["models/*.py", "schemas/*.py"],
                    "import_fix": "from pydantic import BaseModel",
                },
                "HTTPException": {
                    "files": ["routes/*.py", "endpoints/*.py"],
                    "import_fix": "from fastapi import HTTPException",
                },
            }

            # Check for import-related errors
            if "is not defined" in error_message:
                for symbol, pattern_info in import_patterns.items():
                    if symbol in error_message:
                        result["error_type"] = "import_error"
                        result["analysis_details"]["missing_symbol"] = symbol
                        result["analysis_details"]["suggested_import"] = pattern_info[
                            "import_fix"
                        ]

                        # Look for files that use this symbol
                        if project_dir:
                            import glob
                            import os

                            for pattern in pattern_info["files"]:
                                file_pattern = os.path.join(project_dir, pattern)
                                matching_files = glob.glob(file_pattern)

                                for file_path in matching_files:
                                    try:
                                        with open(
                                            file_path, "r", encoding="utf-8"
                                        ) as f:
                                            content = f.read()

                                        if symbol in content:
                                            rel_path = os.path.relpath(
                                                file_path, project_dir
                                            )
                                            result["identified_file"] = rel_path
                                            result["confidence"] = 0.9
                                            result["suggested_fixes"].append(
                                                {
                                                    "type": "add_import",
                                                    "import_statement": pattern_info[
                                                        "import_fix"
                                                    ],
                                                    "line_position": "top",
                                                }
                                            )
                                            break
                                    except Exception as e:
                                        logger.warning(
                                            f"Error reading {file_path}: {e}"
                                        )
                                        continue

                                if result["identified_file"]:
                                    break

            # Analyze traceback if available
            if traceback_text and project_dir:
                import re

                # Extract file paths from traceback
                file_pattern = r'File [\'"]([^"\']+)[\'"]'
                matches = re.findall(file_pattern, traceback_text)

                project_files = []
                for file_path in matches:
                    if project_dir in file_path or not os.path.isabs(file_path):
                        if os.path.isabs(file_path):
                            rel_path = os.path.relpath(file_path, project_dir)
                        else:
                            rel_path = file_path

                        if not rel_path.startswith(".."):
                            project_files.append(rel_path)

                if project_files:
                    # Use the last file in the traceback (usually the actual error location)
                    result["identified_file"] = project_files[-1]
                    result["confidence"] = max(result["confidence"], 0.8)
                    result["analysis_details"]["traceback_files"] = project_files

            logger.info(f"Error analysis result: {result}")
            return result

        except Exception as e:
            logger.error(f"Error during error analysis: {str(e)}", exc_info=True)
            return {
                "identified_file": None,
                "confidence": 0.0,
                "error_type": "analysis_failed",
                "suggested_fixes": [],
                "analysis_details": {"analysis_error": str(e)},
            }
