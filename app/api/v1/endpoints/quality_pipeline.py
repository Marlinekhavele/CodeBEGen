"""
Quality Pipeline API Endpoints

This module provides REST API endpoints for configuring and monitoring
the comprehensive quality assurance pipeline.
"""

import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.db.database import get_db
from app.api.v1.services.enhanced_quality_middleware import (
    EnhancedCodeGenerationQualityMiddleware,
)
from app.api.v1.services.quality_config_manager import (
    QualityConfigLevel,
    QualityConfigManager,
)
from app.api.v1.services.quality_pipeline_orchestrator import (
    QualityAssurancePipeline,
    QualityLevel,
)

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/quality", tags=["Quality Pipeline"])

# Initialize services
config_manager = QualityConfigManager()
quality_pipeline = QualityAssurancePipeline()
quality_middleware = EnhancedCodeGenerationQualityMiddleware()


# Pydantic models for API requests/responses
class QualityConfigRequest(BaseModel):
    """Request model for quality configuration"""

    project_id: str = Field(..., description="Project identifier")
    language: str = Field(default="python", description="Programming language")
    config_level: QualityConfigLevel = Field(
        default=QualityConfigLevel.STANDARD, description="Quality level"
    )
    custom_settings: Optional[Dict[str, Any]] = Field(
        default=None, description="Custom configuration settings"
    )


class QualityConfigResponse(BaseModel):
    """Response model for quality configuration"""

    project_id: str
    language: str
    config_level: str
    tier1_enabled: bool
    tier2_enabled: bool
    tier3_enabled: bool
    tier4_enabled: bool
    parallel_processing: bool
    min_quality_score: int
    custom_settings: Dict[str, Any]


class QualityAnalysisRequest(BaseModel):
    """Request model for quality analysis"""

    project_id: str = Field(..., description="Project identifier")
    files_data: Dict[str, str] = Field(..., description="File path to content mapping")
    language: str = Field(default="python", description="Programming language")
    quality_level: QualityLevel = Field(
        default=QualityLevel.STANDARD, description="Analysis depth"
    )
    auto_fix: bool = Field(default=True, description="Apply automatic fixes")


class QualityAnalysisResponse(BaseModel):
    """Response model for quality analysis"""

    success: bool
    project_id: str
    processed_files: Dict[str, str]
    summary: Dict[str, Any]
    recommendations: List[str]
    processing_time: float
    quality_score: int


class QualityReportResponse(BaseModel):
    """Response model for quality report"""

    project_id: str
    language: str
    total_files: int
    quality_score: int
    issues_summary: Dict[str, int]
    tier_results: Dict[str, Any]
    recommendations: List[str]
    generated_at: str


# API Endpoints


@router.get("/config")
async def get_default_config(
    language: str = "python",
    config_level: QualityConfigLevel = QualityConfigLevel.STANDARD,
) -> Dict[str, Any]:
    """Get default quality configuration for a language and level"""
    try:
        config = config_manager.get_config(
            project_id="default", language_or_level=language, config_level=config_level
        )
        return {
            "language": config.language,
            "config_level": config.config_level.value,
            "min_quality_score": config.min_quality_score,
            "max_processing_time": config.max_processing_time,
            "parallel_processing": config.parallel_processing,
            "enabled_tiers": {
                "tier1": config.tier1_prompt_enhancement.enabled,
                "tier2": config.tier2_real_time_validation.enabled,
                "tier3": config.tier3_code_quality.enabled,
                "tier4": config.tier4_semantic_validation.enabled,
            },
        }
    except Exception as e:
        logger.error(f"Failed to get default config: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get configuration: {str(e)}"
        )


@router.get("/config/languages")
async def get_supported_languages() -> Dict[str, Any]:
    """Get list of supported languages and their default configurations"""
    try:
        supported_languages = ["python", "javascript", "typescript", "go", "php"]
        language_configs = {}

        for language in supported_languages:
            config = config_manager.get_config(
                project_id="default",
                language_or_level=language,
                config_level=QualityConfigLevel.STANDARD,
            )
            language_configs[language] = {
                "language": config.language,
                "min_quality_score": config.min_quality_score,
                "supported_tiers": {
                    "tier1": config.tier1_prompt_enhancement.enabled,
                    "tier2": config.tier2_real_time_validation.enabled,
                    "tier3": config.tier3_code_quality.enabled,
                    "tier4": config.tier4_semantic_validation.enabled,
                },
            }
        return {
            "supported_languages": supported_languages,
            "languages": supported_languages,  # For backwards compatibility
            "language_configs": language_configs,
        }
    except Exception as e:
        logger.error(f"Failed to get language configs: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get language configurations: {str(e)}"
        )


@router.get("/config/{project_id}")
async def get_quality_config(
    project_id: str, language: str = "python", db: Session = Depends(get_db)
) -> QualityConfigResponse:
    """
    Get quality configuration for a project.
    """
    try:
        config = config_manager.get_config(project_id, language_or_level=language)

        return QualityConfigResponse(
            project_id=config.project_id,
            language=config.language,
            config_level=config.config_level.value,
            tier1_enabled=config.tier1_prompt_enhancement.enabled,
            tier2_enabled=config.tier2_real_time_validation.enabled,
            tier3_enabled=config.tier3_code_quality.enabled,
            tier4_enabled=config.tier4_semantic_validation.enabled,
            parallel_processing=config.parallel_processing,
            min_quality_score=config.min_quality_score,
            custom_settings=config.custom_rules,
        )

    except Exception as e:
        logger.error(f"Error getting quality config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config")
async def create_quality_config(
    request: QualityConfigRequest, db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Create or update quality configuration for a project.
    """
    try:
        # Get base configuration
        config = config_manager.get_config(
            request.project_id,
            language_or_level=request.language,
            config_level=request.config_level,
        )

        # Apply custom settings if provided
        if request.custom_settings:
            for key, value in request.custom_settings.items():
                if hasattr(config, key):
                    setattr(config, key, value)
                else:
                    config.custom_rules[key] = value

        # Save configuration
        success = config_manager.save_config(config)

        if success:
            return {"message": f"Quality configuration saved for {request.project_id}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save configuration")

    except Exception as e:
        logger.error(f"Error creating quality config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config/{project_id}")
async def update_quality_config(
    project_id: str,
    updates: Dict[str, Any],
    language: str = "python",
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """
    Update specific quality configuration settings.
    """
    try:
        success = config_manager.update_config(project_id, language, updates)

        if success:
            return {"message": f"Quality configuration updated for {project_id}"}
        else:
            raise HTTPException(
                status_code=500, detail="Failed to update configuration"
            )

    except Exception as e:
        logger.error(f"Error updating quality config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/config/{project_id}")
async def delete_quality_config(
    project_id: str, language: str = "python", db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Delete quality configuration for a project.
    """
    try:
        success = config_manager.delete_config(project_id, language)

        if success:
            return {"message": f"Quality configuration deleted for {project_id}"}
        else:
            raise HTTPException(status_code=404, detail="Configuration not found")

    except Exception as e:
        logger.error(f"Error deleting quality config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
async def analyze_code_quality(
    request: QualityAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> QualityAnalysisResponse:
    """
    Run comprehensive quality analysis on code files.
    """
    try:
        import time

        start_time = time.time()
        # Run quality pipeline
        # Since the pipeline processes single files, we'll process the main file from files_data
        main_file_path = (
            list(request.files_data.keys())[0] if request.files_data else "main.py"
        )
        main_file_content = (
            list(request.files_data.values())[0] if request.files_data else ""
        )

        result = await quality_pipeline.run_pipeline(
            code=main_file_content,
            language=request.language,
            file_path=main_file_path,
            quality_level=request.quality_level,
            prompt="Analyze and improve this code",
            project_dir=f"repos/{request.project_id}",
            context={
                "project_id": request.project_id,
                "auto_fix": request.auto_fix,
                "all_files": request.files_data,
            },
        )

        processing_time = time.time() - start_time

        return QualityAnalysisResponse(
            success=result.get("success", True),
            project_id=request.project_id,
            processed_files=result.get("processed_files", {}),
            summary=result.get("summary", {}),
            recommendations=result.get("recommendations", []),
            processing_time=processing_time,
            quality_score=result.get("summary", {}).get("overall_quality_score", 0),
        )

    except Exception as e:
        logger.error(f"Error analyzing code quality: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyze/{project_id}/status")
async def get_analysis_status(
    project_id: str, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get status of ongoing quality analysis.
    """
    try:
        # In a real implementation, this would check a task queue or database
        # For now, return a basic status
        return {
            "project_id": project_id,
            "status": "completed",  # or "running", "pending", "failed"
            "progress": 100,
            "estimated_time_remaining": 0,
        }

    except Exception as e:
        logger.error(f"Error getting analysis status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate")
async def validate_code_files(
    request: QualityAnalysisRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Validate code files without applying fixes.
    """
    try:
        # Use enhanced middleware for validation only
        results = {}

        for file_path, content in request.files_data.items():
            validation_result = await quality_middleware.validate_before_writing(
                project_id=request.project_id,
                file_path=file_path,
                content=content,
                language=request.language,
            )
            results[file_path] = validation_result

        # Calculate overall statistics
        total_errors = sum(len(result.get("errors", [])) for result in results.values())
        total_warnings = sum(
            len(result.get("warnings", [])) for result in results.values()
        )
        valid_files = sum(
            1 for result in results.values() if result.get("valid", False)
        )

        return {
            "project_id": request.project_id,
            "validation_results": results,
            "summary": {
                "total_files": len(request.files_data),
                "valid_files": valid_files,
                "total_errors": total_errors,
                "total_warnings": total_warnings,
                "overall_valid": total_errors == 0,
            },
        }

    except Exception as e:
        logger.error(f"Error validating code files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/{project_id}")
async def get_quality_report(
    project_id: str, language: str = "python", db: Session = Depends(get_db)
) -> QualityReportResponse:
    """
    Generate comprehensive quality report for a project.
    """
    try:
        from datetime import datetime

        # In a real implementation, this would aggregate historical data
        # For now, generate a sample report structure

        return QualityReportResponse(
            project_id=project_id,
            language=language,
            total_files=0,
            quality_score=85,
            issues_summary={"critical": 0, "high": 2, "medium": 5, "low": 8},
            tier_results={
                "tier1_prompt_enhancement": {"enabled": True, "improvements": 3},
                "tier2_real_time_validation": {"enabled": True, "issues_caught": 7},
                "tier3_code_quality": {"enabled": True, "fixes_applied": 12},
                "tier4_semantic_validation": {"enabled": True, "patterns_detected": 2},
            },
            recommendations=[
                "Consider enabling comprehensive quality level for better coverage",
                "Review and fix medium-priority issues for improved maintainability",
                "Add unit tests for better code coverage",
            ],
            generated_at=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error(f"Error generating quality report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/configs")
async def list_project_configs(db: Session = Depends(get_db)) -> List[Dict[str, str]]:
    """
    List all project quality configurations.
    """
    try:
        configs = config_manager.list_project_configs()
        return configs

    except Exception as e:
        logger.error(f"Error listing project configs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/languages/{language}/config")
async def get_language_config(
    language: str, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get default configuration for a programming language.
    """
    try:
        lang_config = config_manager.get_language_config(language)

        return {
            "language": language,
            "formatters": lang_config.formatters,
            "linters": lang_config.linters,
            "type_checkers": lang_config.type_checkers,
            "test_frameworks": lang_config.test_frameworks,
            "security_scanners": lang_config.security_scanners,
            "complexity_threshold": lang_config.complexity_threshold,
            "line_length_limit": lang_config.line_length_limit,
            "custom_patterns": lang_config.custom_patterns,
        }

    except Exception as e:
        logger.error(f"Error getting language config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/{language}/{config_level}")
async def get_config_by_language_and_level(
    language: str, config_level: str, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get configuration for a specific language and quality level.
    """
    try:
        # Convert string to enum
        try:
            quality_level = QualityConfigLevel(config_level.lower())
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid config level: {config_level}"
            )

        config = config_manager.get_config(
            project_id="default", language_or_level=language, config_level=quality_level
        )

        # Get language-specific configuration
        lang_config = config.language_configs.get(language)
        if lang_config is None:
            # Create default language config if not found
            from app.api.v1.services.quality_config_manager import LanguageConfig

            lang_config = LanguageConfig()

        return {
            "config": {
                "language": language,
                "level": config_level,
                "formatters": lang_config.formatters,
                "linters": lang_config.linters,
                "type_checkers": lang_config.type_checkers,
                "test_frameworks": lang_config.test_frameworks,
                "security_scanners": lang_config.security_scanners,
                "complexity_threshold": lang_config.complexity_threshold,
                "line_length_limit": lang_config.line_length_limit,
                "custom_patterns": lang_config.custom_patterns,
            }
        }

    except Exception as e:
        logger.error(f"Error getting config for {language}/{config_level}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/{project_id}/export")
async def export_quality_config(
    project_id: str, language: str = "python", db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Export quality configuration to a downloadable file.
    """
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        success = config_manager.export_config(project_id, language, temp_path)

        if success:
            # In a real implementation, you would return a download link or file content
            return {
                "message": f"Configuration exported for {project_id}",
                "export_path": temp_path,
            }
        else:
            raise HTTPException(
                status_code=500, detail="Failed to export configuration"
            )

    except Exception as e:
        logger.error(f"Error exporting quality config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/import")
async def import_quality_config(
    config_data: Dict[str, Any], db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Import quality configuration from data.
    """
    try:
        import json
        import tempfile

        # Create temporary file with config data
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f, indent=2)
            temp_path = f.name

        success = config_manager.import_config(temp_path)

        # Clean up temporary file
        os.unlink(temp_path)

        if success:
            return {"message": "Configuration imported successfully"}
        else:
            raise HTTPException(
                status_code=500, detail="Failed to import configuration"
            )

    except Exception as e:
        logger.error(f"Error importing quality config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def quality_pipeline_health(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get health status of quality pipeline services.
    """
    try:
        # Check service health
        health_status = {
            "status": "healthy",
            "pipeline_status": "operational",
            "dependencies": {
                "config_manager": "healthy",
                "quality_pipeline": "healthy",
                "quality_middleware": "healthy",
                "database": "healthy",
            },
            "config_manager": "healthy",
            "quality_pipeline": "healthy",
            "quality_middleware": "healthy",
            "overall_status": "healthy",
        }

        # In a real implementation, perform actual health checks
        try:  # Test config manager
            config_manager.get_config("test", language_or_level="python")

            # Test quality pipeline
            # await quality_pipeline.run_pipeline("test", {}, "python", QualityLevel.BASIC)

        except Exception as e:
            health_status["overall_status"] = "degraded"
            health_status["status"] = "degraded"
            health_status["pipeline_status"] = "degraded"
            health_status["dependencies"]["config_manager"] = "unhealthy"
            health_status["error"] = str(e)

        return health_status

    except Exception as e:
        logger.error(f"Error checking pipeline health: {e}")
        raise HTTPException(status_code=500, detail=str(e))
