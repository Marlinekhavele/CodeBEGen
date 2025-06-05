"""
Enhanced Code Generation Quality Middleware

This enhanced middleware integrates the complete 4-tier quality assurance pipeline
into the code generation workflow, providing comprehensive quality improvement
and validation capabilities.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from .code_generation_quality_middleware import CodeGenerationQualityMiddleware
from .quality_pipeline_orchestrator import (
    AutoFixStrategy,
    QualityAssurancePipeline,
    QualityLevel,
    QualityPipelineConfig,
)

logger = logging.getLogger(__name__)


class EnhancedCodeGenerationQualityMiddleware:
    """
    Enhanced middleware that provides comprehensive quality assurance
    through the 4-tier pipeline system.
    """

    def __init__(self, config: Optional[QualityPipelineConfig] = None):
        # Initialize with default configuration if none provided
        self.config = config or QualityPipelineConfig(
            quality_level=QualityLevel.STANDARD,
            auto_fix_strategy=AutoFixStrategy.MODERATE,
            enable_tier1=True,
            enable_tier2=True,
            enable_tier3=True,
            enable_tier4=False,  # Disabled by default due to cost
            min_quality_score=70.0,
            max_execution_time=30.0,
        )
        # Initialize the quality pipeline
        self.pipeline = QualityAssurancePipeline(self.config)

        # Fallback to original middleware if needed
        self.fallback_middleware = CodeGenerationQualityMiddleware()
        self._original_middleware = self.fallback_middleware  # Add alias for tests

        # Performance tracking
        self.processing_stats = {
            "total_files_processed": 0,
            "total_issues_fixed": 0,
            "average_quality_improvement": 0.0,
            "average_processing_time": 0.0,
        }

    async def process_generated_files(
        self,
        project_id: str,
        generated_files: Dict[str, str],  # file_path -> content
        language: str = "python",
        prompts: Optional[Dict[str, str]] = None,  # file_path -> original_prompt
        auto_fix: bool = True,
        quality_level: Optional[QualityLevel] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process generated files through the enhanced quality pipeline.

        Args:
            project_id: Project identifier
            generated_files: Dictionary of file_path -> file_content
            language: Programming language
            prompts: Optional dictionary of file_path -> original_prompt
            auto_fix: Whether to apply automatic fixes
            quality_level: Quality level to use (overrides config)
            context: Additional context for processing

        Returns:
            Enhanced processing results with comprehensive quality analysis
        """
        start_time = time.time()

        try:
            # Use custom quality level if provided
            current_config = self.config
            if quality_level:
                current_config = QualityPipelineConfig(
                    quality_level=quality_level,
                    auto_fix_strategy=self.config.auto_fix_strategy,
                    enable_tier1=True,
                    enable_tier2=True,
                    enable_tier3=True,
                    enable_tier4=(quality_level == QualityLevel.COMPREHENSIVE),
                    min_quality_score=self.config.min_quality_score,
                    max_execution_time=self.config.max_execution_time,
                )

                # Create new pipeline instance with custom config
                pipeline = QualityAssurancePipeline(current_config)
            else:
                pipeline = self.pipeline

            logger.info(
                f"Processing {len(generated_files)} files with quality level: {current_config.quality_level.value}"
            )

            project_path = f"repos/{project_id}"
            processed_files = {}
            quality_reports = {}
            pipeline_results = {}

            # Enhanced context
            enhanced_context = {
                "project_id": project_id,
                "project_path": project_path,
                "total_files": len(generated_files),
                "language": language,
                **(context or {}),
            }

            # Process files through the pipeline
            total_quality_improvement = 0.0
            total_issues_fixed = 0

            # Process files concurrently if enabled
            if current_config.parallel_processing and len(generated_files) > 1:
                tasks = []
                for file_path, content in generated_files.items():
                    prompt = prompts.get(file_path, "") if prompts else ""
                    task = self._process_single_file_pipeline(
                        pipeline,
                        prompt,
                        content,
                        file_path,
                        language,
                        project_path,
                        enhanced_context,
                    )
                    tasks.append((file_path, task))

                # Execute tasks concurrently
                for file_path, task in tasks:
                    try:
                        pipeline_result = await task
                        processed_files[file_path] = (
                            pipeline_result.final_code
                            if auto_fix
                            else generated_files[file_path]
                        )
                        pipeline_results[file_path] = pipeline_result

                        # Calculate improvements
                        quality_improvement = pipeline_result.quality_score
                        total_quality_improvement += quality_improvement
                        total_issues_fixed += len(pipeline_result.issues_fixed)

                        logger.info(
                            f"Pipeline completed for {file_path}: {quality_improvement:.1f}% quality"
                        )

                    except Exception as e:
                        logger.error(f"Pipeline failed for {file_path}: {str(e)}")
                        # Fallback to original processing
                        processed_files[file_path] = generated_files[file_path]
                        pipeline_results[file_path] = None

            else:
                # Sequential processing
                for file_path, content in generated_files.items():
                    try:
                        prompt = prompts.get(file_path, "") if prompts else ""

                        # Process through pipeline
                        pipeline_result = await self._process_single_file_pipeline(
                            pipeline,
                            prompt,
                            content,
                            file_path,
                            language,
                            project_path,
                            enhanced_context,
                        )

                        # Use improved code if auto_fix is enabled
                        processed_files[file_path] = (
                            pipeline_result.final_code if auto_fix else content
                        )
                        pipeline_results[file_path] = pipeline_result

                        # Track improvements
                        quality_improvement = pipeline_result.quality_score
                        total_quality_improvement += quality_improvement
                        total_issues_fixed += len(pipeline_result.issues_fixed)

                        logger.info(
                            f"Pipeline completed for {file_path}: {quality_improvement:.1f}% quality in {pipeline_result.total_execution_time:.2f}s"
                        )

                    except Exception as e:
                        logger.error(f"Pipeline failed for {file_path}: {str(e)}")

                        # Fallback to original middleware
                        logger.info(
                            f"Falling back to original middleware for {file_path}"
                        )
                        fallback_result = (
                            await self.fallback_middleware.process_generated_files(
                                project_id, {file_path: content}, language, auto_fix
                            )
                        )
                        processed_files[file_path] = fallback_result[
                            "processed_files"
                        ].get(file_path, content)
                        pipeline_results[file_path] = None

            # Generate quality reports
            for file_path, pipeline_result in pipeline_results.items():
                if pipeline_result:
                    quality_reports[file_path] = self._generate_quality_report(
                        pipeline_result
                    )
                else:
                    quality_reports[file_path] = {
                        "status": "fallback_used",
                        "quality_score": 0.0,
                        "issues_found": 0,
                        "issues_fixed": 0,
                    }

            # Calculate summary statistics
            avg_quality = total_quality_improvement / max(1, len(generated_files))
            total_execution_time = time.time() - start_time

            # Update processing stats
            self._update_processing_stats(
                len(generated_files),
                total_issues_fixed,
                avg_quality,
                total_execution_time,
            )

            # Compile comprehensive summary
            summary = {
                "files_processed": len(generated_files),
                "files_improved": len(
                    [r for r in pipeline_results.values() if r and r.quality_score > 70]
                ),
                "total_issues_found": sum(
                    len(r.issues_detected) for r in pipeline_results.values() if r
                ),
                "total_issues_fixed": total_issues_fixed,
                "average_quality_score": avg_quality,
                "total_execution_time": total_execution_time,
                "pipeline_config": {
                    "quality_level": current_config.quality_level.value,
                    "auto_fix_strategy": current_config.auto_fix_strategy.value,
                    "tiers_enabled": {
                        "tier1": current_config.enable_tier1,
                        "tier2": current_config.enable_tier2,
                        "tier3": current_config.enable_tier3,
                        "tier4": current_config.enable_tier4,
                    },
                },
                "recommendations": await self._generate_project_recommendations(
                    pipeline_results, current_config
                ),
            }

            logger.info(
                f"Enhanced quality processing completed: {avg_quality:.1f}% average quality, {total_issues_fixed} issues fixed"
            )

            return {
                "processed_files": processed_files,
                "quality_reports": quality_reports,
                "pipeline_results": {
                    k: self._serialize_pipeline_result(v)
                    for k, v in pipeline_results.items()
                },
                "summary": summary,
                "processing_stats": self.processing_stats.copy(),
            }

        except Exception as e:
            logger.error(
                f"Enhanced middleware processing failed: {str(e)}", exc_info=True
            )

            # Fallback to original middleware
            logger.info("Falling back to original quality middleware")
            fallback_result = await self.fallback_middleware.process_generated_files(
                project_id, generated_files, language, auto_fix
            )

            # Add error information
            fallback_result["enhanced_middleware_error"] = str(e)
            fallback_result["fallback_used"] = True

            return fallback_result

    async def _process_single_file_pipeline(
        self,
        pipeline: QualityAssurancePipeline,
        prompt: str,
        content: str,
        file_path: str,
        language: str,
        project_path: str,
        context: Dict[str, Any],
    ):
        """Process a single file through the quality pipeline."""
        return await pipeline.process_code_generation(
            prompt=prompt,
            code=content,
            file_path=file_path,
            language=language,
            project_dir=project_path,
            context=context,
        )

    def _generate_quality_report(self, pipeline_result) -> Dict[str, Any]:
        """Generate a quality report from pipeline result."""
        return {
            "quality_score": pipeline_result.quality_score,
            "issues_found": len(pipeline_result.issues_detected),
            "issues_fixed": len(pipeline_result.issues_fixed),
            "remaining_issues": len(pipeline_result.remaining_issues),
            "iterations_performed": pipeline_result.iterations_performed,
            "execution_time": pipeline_result.total_execution_time,
            "tier_results": {
                "tier1_success": pipeline_result.tier1_result is not None
                and pipeline_result.tier1_result.get("success", False),
                "tier2_success": pipeline_result.tier2_result is not None
                and pipeline_result.tier2_result.get("success", False),
                "tier3_success": pipeline_result.tier3_result is not None
                and pipeline_result.tier3_result.get("success", False),
                "tier4_success": pipeline_result.tier4_result is not None
                and pipeline_result.tier4_result.get("success", False),
            },
            "improvements_applied": len(pipeline_result.issues_fixed) > 0,
            "improvement_suggestions": pipeline_result.improvement_suggestions,
            "status": "completed",
        }

    def _serialize_pipeline_result(self, pipeline_result) -> Optional[Dict[str, Any]]:
        """Serialize pipeline result for JSON response."""
        if not pipeline_result:
            return None

        return {
            "original_code_length": len(pipeline_result.original_code),
            "final_code_length": len(pipeline_result.final_code),
            "quality_score": pipeline_result.quality_score,
            "total_execution_time": pipeline_result.total_execution_time,
            "iterations_performed": pipeline_result.iterations_performed,
            "issues_detected_count": len(pipeline_result.issues_detected),
            "issues_fixed_count": len(pipeline_result.issues_fixed),
            "remaining_issues_count": len(pipeline_result.remaining_issues),
            "tier_execution_times": pipeline_result.tier_execution_times,
            "improvement_suggestions_count": len(
                pipeline_result.improvement_suggestions
            ),
            "code_improved": pipeline_result.final_code
            != pipeline_result.original_code,
        }

    async def _generate_project_recommendations(
        self, pipeline_results: Dict[str, Any], config: QualityPipelineConfig
    ) -> List[Dict[str, Any]]:
        """Generate project-level recommendations based on all file results."""
        recommendations = []

        # Analyze overall quality
        successful_results = [r for r in pipeline_results.values() if r]
        if successful_results:
            avg_quality = sum(r.quality_score for r in successful_results) / len(
                successful_results
            )

            if avg_quality < 60:
                recommendations.append(
                    {
                        "type": "quality_improvement",
                        "priority": "high",
                        "description": f"Project average quality ({avg_quality:.1f}%) is below recommended threshold",
                        "suggestions": [
                            "Enable Tier 4 semantic validation for comprehensive analysis",
                            "Use AGGRESSIVE auto-fix strategy",
                            "Review and improve code generation prompts",
                        ],
                    }
                )  # Check for common issues across files
            all_issues = []
            for result in successful_results:
                # Handle both list and int types for remaining_issues
                if hasattr(result, "remaining_issues"):
                    remaining_issues = result.remaining_issues
                    if isinstance(remaining_issues, (list, tuple)):
                        all_issues.extend(remaining_issues)
                    elif isinstance(remaining_issues, int):
                        # If it's an int, we can't iterate over it, skip
                        continue
                    else:
                        # Try to convert to list if it's another iterable
                        try:
                            all_issues.extend(list(remaining_issues))
                        except (TypeError, ValueError):
                            # Skip if we can't convert to iterable
                            continue

            # Group issues by type
            issue_types = {}
            for issue in all_issues:
                issue_type = issue.get("type", "unknown")
                issue_types[issue_type] = issue_types.get(issue_type, 0) + 1

            # Recommend solutions for common issues
            if issue_types.get("undefined_variable", 0) > 2:
                recommendations.append(
                    {
                        "type": "pattern_improvement",
                        "priority": "medium",
                        "description": "Multiple undefined variable errors detected across files",
                        "suggestions": [
                            "Improve prompt context with variable definitions",
                            "Enable more aggressive auto-fixing",
                            "Add project-specific context to prompts",
                        ],
                    }
                )

        # Performance recommendations
        total_execution_time = sum(
            r.total_execution_time for r in successful_results if r
        )
        if total_execution_time > config.max_execution_time * 0.8:
            recommendations.append(
                {
                    "type": "performance",
                    "priority": "low",
                    "description": "Quality processing is approaching time limits",
                    "suggestions": [
                        "Enable parallel processing",
                        "Disable Tier 4 for faster processing",
                        "Increase execution time limit if needed",
                    ],
                }
            )

        return recommendations

    def _update_processing_stats(
        self,
        files_processed: int,
        issues_fixed: int,
        avg_quality: float,
        execution_time: float,
    ) -> None:
        """Update processing statistics."""
        prev_total = self.processing_stats["total_files_processed"]

        # Update totals
        self.processing_stats["total_files_processed"] += files_processed
        self.processing_stats["total_issues_fixed"] += issues_fixed

        # Update averages
        if prev_total > 0:
            prev_avg_quality = self.processing_stats["average_quality_improvement"]
            prev_avg_time = self.processing_stats["average_processing_time"]

            new_total = self.processing_stats["total_files_processed"]

            self.processing_stats["average_quality_improvement"] = (
                prev_avg_quality * prev_total + avg_quality * files_processed
            ) / new_total
            self.processing_stats["average_processing_time"] = (
                prev_avg_time * prev_total + execution_time
            ) / new_total
        else:
            self.processing_stats["average_quality_improvement"] = avg_quality
            self.processing_stats["average_processing_time"] = execution_time

    async def get_processing_insights(self) -> Dict[str, Any]:
        """Get insights about processing performance and quality trends."""
        return {
            "performance_stats": self.processing_stats.copy(),
            "pipeline_status": self.pipeline.get_pipeline_status(),
            "configuration": {
                "quality_level": self.config.quality_level.value,
                "auto_fix_strategy": self.config.auto_fix_strategy.value,
                "enabled_tiers": {
                    "tier1": self.config.enable_tier1,
                    "tier2": self.config.enable_tier2,
                    "tier3": self.config.enable_tier3,
                    "tier4": self.config.enable_tier4,
                },
                "quality_threshold": self.config.min_quality_score,
                "max_execution_time": self.config.max_execution_time,
            },
            "recommendations": [
                {
                    "type": "efficiency",
                    "description": "Consider enabling parallel processing for multiple files",
                    "applicable": True,
                },
                {
                    "type": "quality",
                    "description": "Enable Tier 4 for comprehensive semantic validation",
                    "applicable": not self.config.enable_tier4,
                },
            ],
        }

    # Backward compatibility methods
    async def apply_quality_checks(
        self, content: str, file_path: str, project_id: str, language: str = "python"
    ) -> str:
        """
        Apply quality checks to a single file (backward compatibility method).

        This method provides backward compatibility with the existing
        CodeGenerationService integration while leveraging the enhanced pipeline.

        Args:
            content: Code content to process
            file_path: Path to the file
            project_id: Project identifier
            language: Programming language

        Returns:
            Improved code content
        """
        try:
            # Process single file through enhanced pipeline
            result = await self.process_generated_files(
                project_id=project_id,
                generated_files={file_path: content},
                language=language,
                prompts=None,
                auto_fix=True,
                quality_level=None,  # Use default config
                context={"single_file_mode": True},
            )

            # Extract the processed content
            processed_files = result.get("processed_files", {})
            return processed_files.get(file_path, content)

        except Exception as e:
            logger.error(f"Enhanced quality check failed for {file_path}: {str(e)}")

            # Fallback to original middleware
            try:
                fallback_result = (
                    await self.fallback_middleware.process_generated_files(
                        project_id, {file_path: content}, language, auto_fix=True
                    )
                )
                return fallback_result["processed_files"].get(file_path, content)
            except Exception as fallback_error:
                logger.error(
                    f"Fallback quality check also failed: {str(fallback_error)}"
                )
                return content

    async def validate_realtime(
        self, code: str, language: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Perform real-time validation on code using Tier 2 of the quality pipeline.

        Args:
            code: Code to validate
            language: Programming language
            context: Additional context including project_id, entity_name, component_type

        Returns:
            Dictionary with validation results including validated_code and issues
        """
        try:
            project_id = context.get("project_id", "unknown")

            # Process through pipeline for real-time validation
            result = await self.process_generated_files(
                project_id=project_id,
                generated_files={"temp_file": code},
                language=language,
                prompts=None,
                auto_fix=True,
                quality_level=QualityLevel.STANDARD,  # Use standard for real-time
                context={**context, "validation_mode": "realtime"},
            )

            processed_files = result.get("processed_files", {})
            quality_reports = result.get("quality_reports", {})

            validated_code = processed_files.get("temp_file", code)
            quality_report = quality_reports.get("temp_file", {})

            return {
                "validated_code": validated_code,
                "issues": quality_report.get("remaining_issues", []),
                "quality_score": quality_report.get("quality_score", 100),
                "validation_success": quality_report.get("quality_score", 100) >= 70,
                "improvements_applied": validated_code != code,
                "execution_time": quality_report.get("execution_time", 0.0),
            }
        except Exception as e:
            logger.error(f"Real-time validation failed: {str(e)}")
            # Return original code with error indication
            return {
                "validated_code": code,
                "issues": [{"type": "validation_error", "message": str(e)}],
                "quality_score": 50,
                "validation_success": False,
                "improvements_applied": False,
                "execution_time": 0.0,
            }

    async def process_code_quality(
        self,
        code: str,
        language: str,
        quality_level: QualityLevel,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process code quality using Tier 3 auto-fixing and enhancement.

        Args:
            code: Code to enhance
            language: Programming language
            quality_level: Quality level for processing
            context: Additional context including project_id, entity_name, validation_issues

        Returns:
            Dictionary with enhanced code and quality metrics
        """
        try:
            project_id = context.get("project_id", "unknown")

            # Process through enhanced pipeline
            result = await self.process_generated_files(
                project_id=project_id,
                generated_files={"temp_file": code},
                language=language,
                prompts=None,
                auto_fix=True,
                quality_level=quality_level,
                context={**context, "processing_mode": "quality_enhancement"},
            )

            processed_files = result.get("processed_files", {})
            quality_reports = result.get("quality_reports", {})

            enhanced_code = processed_files.get("temp_file", code)
            quality_report = quality_reports.get("temp_file", {})

            return {
                "enhanced_code": enhanced_code,
                "quality_score": quality_report.get("quality_score", 100),
                "issues_fixed": quality_report.get("issues_fixed", 0),
                "remaining_issues": quality_report.get("remaining_issues", []),
                "improvements_applied": enhanced_code != code,
                "execution_time": quality_report.get("execution_time", 0.0),
                "enhancement_success": quality_report.get("quality_score", 100) >= 70,
            }

        except Exception as e:
            logger.error(f"Code quality processing failed: {str(e)}")
            return {
                "enhanced_code": code,
                "quality_score": 50,
                "issues_fixed": 0,
                "remaining_issues": [{"type": "processing_error", "message": str(e)}],
                "improvements_applied": False,
                "execution_time": 0.0,
                "enhancement_success": False,
            }

    async def perform_semantic_validation(
        self, components: Dict[str, Any], language: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Perform semantic validation using Tier 4 of the quality pipeline.

        Args:
            components: Dictionary of components to validate
            language: Programming language
            context: Additional context including project_id, entity_name

        Returns:
            Dictionary with semantic validation results
        """
        try:
            project_id = context.get("project_id", "unknown")

            # Convert components to files for pipeline processing
            files_to_validate = {}
            for component_name, component_data in components.items():
                if (
                    isinstance(component_data, dict)
                    and "generated_code" in component_data
                ):
                    file_path = component_data.get("file_path", f"{component_name}.py")
                    files_to_validate[file_path] = component_data["generated_code"]
                elif isinstance(component_data, str):
                    files_to_validate[f"{component_name}.py"] = component_data

            if not files_to_validate:
                return {
                    "validation_success": True,
                    "semantic_issues": [],
                    "quality_score": 100,
                    "recommendations": [],
                    "execution_time": 0.0,
                }

            # Process through comprehensive pipeline with Tier 4 enabled
            result = await self.process_generated_files(
                project_id=project_id,
                generated_files=files_to_validate,
                language=language,
                prompts=None,
                auto_fix=False,  # Don't auto-fix during validation
                quality_level=QualityLevel.COMPREHENSIVE,  # Enable Tier 4
                context={**context, "validation_mode": "semantic"},
            )

            quality_reports = result.get("quality_reports", {})
            summary = result.get("summary", {})

            # Aggregate semantic validation results
            all_semantic_issues = []
            total_quality = 0
            file_count = 0

            for file_path, report in quality_reports.items():
                if report:
                    all_semantic_issues.extend(report.get("remaining_issues", []))
                    total_quality += report.get("quality_score", 100)
                    file_count += 1

            avg_quality = total_quality / max(1, file_count)

            return {
                "validation_success": avg_quality >= 70,
                "semantic_issues": all_semantic_issues,
                "quality_score": avg_quality,
                "recommendations": summary.get("recommendations", []),
                "execution_time": summary.get("total_execution_time", 0.0),
                "files_validated": file_count,
                "tier4_enabled": True,
            }

        except Exception as e:
            logger.error(f"Semantic validation failed: {str(e)}")
            return {
                "validation_success": False,
                "semantic_issues": [{"type": "validation_error", "message": str(e)}],
                "quality_score": 50,
                "recommendations": [],
                "execution_time": 0.0,
                "files_validated": 0,
                "tier4_enabled": False,
            }

    async def validate_architecture(
        self, components: Dict[str, Any], language: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate architectural compliance and integration patterns.

        Args:
            components: Dictionary of components to validate
            language: Programming language
            context: Additional context including project_id, entity_name

        Returns:
            Dictionary with architectural validation results
        """
        try:
            # Delegate to semantic validation for architectural analysis
            validation_result = await self.perform_semantic_validation(
                components, language, {**context, "focus": "architecture"}
            )

            # Extract architectural-specific issues
            semantic_issues = validation_result.get("semantic_issues", [])
            architectural_issues = [
                issue
                for issue in semantic_issues
                if issue.get("category")
                in ["architecture", "design_pattern", "integration"]
            ]

            return {
                "architectural_compliance": len(architectural_issues) == 0,
                "architectural_issues": architectural_issues,
                "compliance_score": validation_result.get("quality_score", 100),
                "recommendations": validation_result.get("recommendations", []),
                "validation_success": validation_result.get("validation_success", True),
                "execution_time": validation_result.get("execution_time", 0.0),
            }

        except Exception as e:
            logger.error(f"Architecture validation failed: {str(e)}")
            return {
                "architectural_compliance": False,
                "architectural_issues": [
                    {"type": "validation_error", "message": str(e)}
                ],
                "compliance_score": 50,
                "recommendations": [],
                "validation_success": False,
                "execution_time": 0.0,
            }

    async def enhance_prompt(
        self, original_prompt: str, language: str, context: Dict[str, Any]
    ) -> str:
        """
        Enhance prompts using Tier 1 of the quality pipeline.

        Args:
            original_prompt: Original prompt to enhance
            language: Programming language
            context: Additional context including project_id, entity_name

        Returns:
            Enhanced prompt string
        """
        try:
            project_id = context.get("project_id", "unknown")

            # Create a temporary pipeline configuration focused on Tier 1
            tier1_config = QualityPipelineConfig(
                quality_level=QualityLevel.BASIC,
                auto_fix_strategy=AutoFixStrategy.CONSERVATIVE,
                enable_tier1=True,
                enable_tier2=False,
                enable_tier3=False,
                enable_tier4=False,
                min_quality_score=70.0,
                max_execution_time=10.0,  # Quick processing for prompt enhancement
            )

            # Create temporary pipeline instance for prompt enhancement
            temp_pipeline = QualityAssurancePipeline(tier1_config)

            # Process prompt enhancement
            enhanced_context = {
                "project_id": project_id,
                "language": language,
                "mode": "prompt_enhancement",
                **(context or {}),
            }

            # Use pipeline's prompt enhancement capability
            pipeline_result = await temp_pipeline.process_code_generation(
                prompt=original_prompt,
                code="",  # Empty code for prompt-only enhancement
                file_path="prompt_enhancement",
                language=language,
                project_dir=f"repos/{project_id}",
                context=enhanced_context,
            )

            # Extract enhanced prompt from Tier 1 result
            if (
                pipeline_result.tier1_result
                and pipeline_result.tier1_result.get("success")
                and "enhanced_prompt" in pipeline_result.tier1_result
            ):
                enhanced_prompt = pipeline_result.tier1_result["enhanced_prompt"]

                # Ensure we don't return the placeholder "ENHANCED" string
                if (
                    enhanced_prompt
                    and enhanced_prompt != "ENHANCED"
                    and enhanced_prompt.strip()
                ):
                    logger.info(
                        f"Prompt enhanced from {len(original_prompt)} to {len(enhanced_prompt)} characters"
                    )
                    return enhanced_prompt

            # Fallback: return original prompt if enhancement failed or returned placeholder
            logger.warning(
                "Prompt enhancement returned placeholder or failed, using original prompt"
            )
            return original_prompt

        except Exception as e:
            logger.error(f"Prompt enhancement failed: {str(e)}")
            # Return original prompt on error
            return original_prompt
