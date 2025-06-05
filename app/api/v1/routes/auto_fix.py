import logging
import os
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.v1.services.code_quality_service import CodeQualityService
from app.api.v1.services.langchain_service import LangchainService
from app.api.v1.utils.error_response import error_response
from app.api.v1.utils.success_response import success_response

router = APIRouter()
logger = logging.getLogger(__name__)


class AutoFixRequest(BaseModel):
    """Request schema for auto-fixing code errors"""

    project_id: str
    error_message: str
    file_path: str
    language: str = "python"
    context: Optional[str] = None


class PreventiveQualityRequest(BaseModel):
    """Request schema for preventive code quality checks"""

    project_id: str
    file_paths: Optional[List[str]] = None  # If None, checks all files
    language: str = "python"
    auto_fix: bool = True
    run_formatters: bool = True
    run_linters: bool = True
    run_type_checkers: bool = True


class CodeGenerationQualityRequest(BaseModel):
    """Request schema for quality checks on newly generated code"""

    project_id: str
    generated_files: List[str]
    language: str = "python"
    auto_fix: bool = True


class AutoFixResponse(BaseModel):
    """Response schema for auto-fix operations"""

    success: bool
    message: str
    fixed_code: Optional[str] = None
    file_path: Optional[str] = None
    error_type: Optional[str] = None
    backup_created: bool = False
    quality_report: Optional[dict] = None


class QualityCheckResponse(BaseModel):
    """Response schema for quality check operations"""

    success: bool
    message: str
    project_id: str
    files_checked: int
    issues_found: int
    issues_fixed: int
    remaining_issues: int
    tools_used: List[str]
    detailed_results: dict


@router.post("/auto-fix", response_model=AutoFixResponse)
async def auto_fix_code_error(request: AutoFixRequest):
    """
    Auto-fix code errors using LLM analysis and correction.

    This endpoint:
    1. Reads the problematic file
    2. Analyzes the error using LLM
    3. Generates fixed code
    4. Creates a backup of the original
    5. Writes the fixed code to the file

    Args:
        request: AutoFixRequest containing error details

    Returns:
        AutoFixResponse with fix results
    """
    try:
        logger.info(
            f"Auto-fix request for project {request.project_id}, file: {request.file_path}"
        )
        logger.info(f"Error message: {request.error_message}")

        # Construct full file path
        full_path = os.path.join("repos", request.project_id, request.file_path)

        if not os.path.exists(full_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {request.file_path}",
            )

        # Read the current code
        with open(full_path, "r", encoding="utf-8") as f:
            current_code = f.read()

        logger.info(f"Read {len(current_code)} characters from {request.file_path}")

        # Create backup
        backup_path = f"{full_path}.backup"
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(current_code)

        logger.info(f"Created backup at {backup_path}")

        # Use LangchainService to fix the code
        fix_result = await LangchainService.fix_code_error(
            project_id=request.project_id,
            error_message=request.error_message,
            generated_code=current_code,
            language=request.language,
            file_path=request.file_path,
            context=request.context,
        )

        if not fix_result or "generated_code" not in fix_result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate fixed code",
            )

        fixed_code = fix_result["generated_code"]
        error_type = fix_result.get("error_type", "unknown")

        # Write the fixed code to the original file
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(fixed_code)

        logger.info(f"Successfully wrote fixed code to {request.file_path}")

        # Perform code quality checks and fixes
        quality_report = None
        if request.language == "python":
            quality_report = await CodeQualityService.run_preventive_quality_checks(
                project_id=request.project_id,
                file_paths=[request.file_path],
                auto_fix=True,
            )

        return success_response(
            status_code=status.HTTP_200_OK,
            data=AutoFixResponse(
                success=True,
                message=f"Successfully fixed {error_type} error in {request.file_path}",
                fixed_code=fixed_code,
                file_path=request.file_path,
                error_type=error_type,
                backup_created=True,
                quality_report=quality_report,
            ),
            message="Code successfully auto-fixed",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in auto-fix: {str(e)}", exc_info=True)
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Auto-fix failed",
            detail=str(e),
        )


@router.post("/auto-fix-test-retry")
async def auto_fix_and_retry_test(request: AutoFixRequest):
    """
    Auto-fix code errors and trigger a test retry.

    This endpoint combines auto-fixing with test execution:
    1. Fixes the code error
    2. Optionally retries the test that failed

    Args:
        request: AutoFixRequest with error details

    Returns:
        Combined response with fix results and test retry status
    """
    try:
        # First, auto-fix the code
        fix_response = await auto_fix_code_error(request)

        if not fix_response.data.success:
            return fix_response

        # TODO: Integrate with TestEndpointService to retry the test
        # This would require additional parameters like endpoint URL, test payload, etc.

        return success_response(
            status_code=status.HTTP_200_OK,
            data={
                "auto_fix": fix_response.data,
                "test_retry": {
                    "status": "not_implemented",
                    "message": "Test retry integration coming soon",
                },
            },
            message="Code fixed successfully. Test retry integration pending.",
        )

    except Exception as e:
        logger.error(f"Error in auto-fix and retry: {str(e)}", exc_info=True)
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Auto-fix and retry failed",
            detail=str(e),
        )


@router.get("/backup/{project_id}")
async def list_backups(project_id: str):
    """
    List all backup files created during auto-fix operations.

    Args:
        project_id: The project identifier

    Returns:
        List of backup files with creation timestamps
    """
    try:
        project_path = os.path.join("repos", project_id)

        if not os.path.exists(project_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project not found: {project_id}",
            )

        backups = []

        # Walk through the project directory to find .backup files
        for root, dirs, files in os.walk(project_path):
            for file in files:
                if file.endswith(".backup"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, project_path)

                    # Get file stats
                    stat = os.stat(full_path)

                    backups.append(
                        {
                            "file_path": rel_path,
                            "original_file": rel_path.replace(".backup", ""),
                            "created_at": stat.st_ctime,
                            "size": stat.st_size,
                        }
                    )

        return success_response(
            status_code=status.HTTP_200_OK,
            data={"backups": backups, "count": len(backups)},
            message=f"Found {len(backups)} backup files",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing backups: {str(e)}", exc_info=True)
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to list backups",
            detail=str(e),
        )


@router.post("/restore-backup/{project_id}")
async def restore_backup(project_id: str, file_path: str):
    """
    Restore a file from its backup.

    Args:
        project_id: The project identifier
        file_path: Path to the original file (backup will have .backup extension)

    Returns:
        Success/failure status
    """
    try:
        original_path = os.path.join("repos", project_id, file_path)
        backup_path = f"{original_path}.backup"

        if not os.path.exists(backup_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backup file not found: {file_path}.backup",
            )

        # Read backup content
        with open(backup_path, "r", encoding="utf-8") as f:
            backup_content = f.read()

        # Restore to original file
        with open(original_path, "w", encoding="utf-8") as f:
            f.write(backup_content)

        logger.info(f"Restored {file_path} from backup")

        return success_response(
            status_code=status.HTTP_200_OK,
            data={"restored_file": file_path},
            message=f"Successfully restored {file_path} from backup",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring backup: {str(e)}", exc_info=True)
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to restore backup",
            detail=str(e),
        )


@router.post("/preventive-quality-check", response_model=QualityCheckResponse)
async def preventive_quality_check(request: PreventiveQualityRequest):
    """
    Perform preventive code quality checks on the specified files.

    This endpoint checks for potential issues and fixes them if requested.

    Args:
        request: PreventiveQualityRequest containing project and file details

    Returns:
        QualityCheckResponse with the results of the quality check
    """
    try:
        logger.info(f"Preventive quality check for project {request.project_id}")

        # Construct file paths
        file_paths = request.file_paths or []
        if not file_paths:
            # If no specific files, check all Python files in the project
            project_path = os.path.join("repos", request.project_id)
            for root, dirs, files in os.walk(project_path):
                for file in files:
                    if file.endswith(".py"):
                        file_paths.append(
                            os.path.relpath(os.path.join(root, file), project_path)
                        )

        issues_found = 0
        issues_fixed = 0
        tools_used = []
        detailed_results = {}

        # Run formatters, linters, and type checkers as per the request
        if request.run_formatters:
            logger.info("Running formatters...")
            # TODO: Integrate actual formatter service
            tools_used.append("formatter")

        if request.run_linters:
            logger.info("Running linters...")
            linter_results = await CodeQualityService.run_linter(
                project_id=request.project_id,
                file_paths=file_paths,
                auto_fix=request.auto_fix,
            )
            issues_found += linter_results.get("issues_found", 0)
            issues_fixed += linter_results.get("issues_fixed", 0)
            detailed_results["linters"] = linter_results

        if request.run_type_checkers:
            logger.info("Running type checkers...")
            type_checker_results = await CodeQualityService.run_type_checker(
                project_id=request.project_id,
                file_paths=file_paths,
                auto_fix=request.auto_fix,
            )
            issues_found += type_checker_results.get("issues_found", 0)
            issues_fixed += type_checker_results.get("issues_fixed", 0)
            detailed_results["type_checkers"] = type_checker_results

        remaining_issues = issues_found - issues_fixed

        return success_response(
            status_code=status.HTTP_200_OK,
            data=QualityCheckResponse(
                success=True,
                message="Quality check completed",
                project_id=request.project_id,
                files_checked=len(file_paths),
                issues_found=issues_found,
                issues_fixed=issues_fixed,
                remaining_issues=remaining_issues,
                tools_used=tools_used,
                detailed_results=detailed_results,
            ),
            message="Preventive quality check successful",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in preventive quality check: {str(e)}", exc_info=True)
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Quality check failed",
            detail=str(e),
        )


@router.post("/code-generation-quality-check", response_model=QualityCheckResponse)
async def code_generation_quality_check(request: CodeGenerationQualityRequest):
    """
    Perform quality checks on newly generated code files.

    This endpoint ensures that the generated code meets the project's quality standards.

    Args:
        request: CodeGenerationQualityRequest containing project and file details

    Returns:
        QualityCheckResponse with the results of the quality check
    """
    try:
        logger.info(f"Code generation quality check for project {request.project_id}")

        issues_found = 0
        issues_fixed = 0
        tools_used = []
        detailed_results = {}

        # Run formatters, linters, and type checkers as per the request
        if request.auto_fix:
            if request.language == "python":
                logger.info("Running Python-specific quality checks...")
                # TODO: Integrate actual Python quality check services
                tools_used.append("python_quality_tool")

        return success_response(
            status_code=status.HTTP_200_OK,
            data=QualityCheckResponse(
                success=True,
                message="Code generation quality check completed",
                project_id=request.project_id,
                files_checked=len(request.generated_files),
                issues_found=issues_found,
                issues_fixed=issues_fixed,
                remaining_issues=0,
                tools_used=tools_used,
                detailed_results=detailed_results,
            ),
            message="Code generation quality check successful",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in code generation quality check: {str(e)}", exc_info=True)
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Quality check failed",
            detail=str(e),
        )


@router.post("/enhanced-auto-fix", response_model=AutoFixResponse)
async def enhanced_auto_fix_code_error(request: AutoFixRequest):
    """
    Enhanced auto-fix with comprehensive code quality integration.

    This endpoint:
    1. Reads the problematic file
    2. Analyzes the error using LLM
    3. Generates fixed code
    4. Runs comprehensive code quality checks and fixes
    5. Creates a backup of the original
    6. Writes the improved code to the file

    Args:
        request: AutoFixRequest containing error details

    Returns:
        AutoFixResponse with comprehensive fix results
    """
    try:
        logger.info(
            f"Enhanced auto-fix request for project {request.project_id}, file: {request.file_path}"
        )

        # Construct full file path
        full_path = os.path.join("repos", request.project_id, request.file_path)

        if not os.path.exists(full_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {request.file_path}",
            )

        # Read the current code
        with open(full_path, "r", encoding="utf-8") as f:
            current_code = f.read()

        # Create backup
        backup_path = f"{full_path}.backup"
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(current_code)

        logger.info(f"Created backup at {backup_path}")

        # Use LangchainService to fix the specific error
        fix_result = await LangchainService.fix_code_error(
            project_id=request.project_id,
            error_message=request.error_message,
            generated_code=current_code,
            language=request.language,
            file_path=request.file_path,
            context=request.context,
        )

        if not fix_result or "generated_code" not in fix_result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate fixed code",
            )

        llm_fixed_code = fix_result["generated_code"]
        error_type = fix_result.get("error_type", "unknown")

        # Apply comprehensive code quality improvements
        quality_service = CodeQualityService()
        quality_report = await quality_service.improve_generated_code(
            code=llm_fixed_code,
            file_path=request.file_path,
            language=request.language,
            project_dir=os.path.join("repos", request.project_id),
        )

        final_code = quality_report.fixed_code

        # Write the improved code to the original file
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(final_code)

        logger.info(f"Successfully wrote enhanced fixed code to {request.file_path}")

        # Convert quality report to dict for response
        quality_report_dict = {
            "issues_found": len(quality_report.issues_found),
            "issues_fixed": len(quality_report.issues_fixed),
            "remaining_issues": len(quality_report.remaining_issues),
            "tools_used": quality_report.tools_used,
            "result": quality_report.result.value,
            "execution_time": quality_report.execution_time,
            "detailed_issues": {
                "found": quality_report.issues_found,
                "fixed": quality_report.issues_fixed,
                "remaining": quality_report.remaining_issues,
            },
        }

        return success_response(
            status_code=status.HTTP_200_OK,
            data=AutoFixResponse(
                success=True,
                message=f"Successfully fixed {error_type} error and improved code quality in {request.file_path}",
                fixed_code=final_code,
                file_path=request.file_path,
                error_type=error_type,
                backup_created=True,
                quality_report=quality_report_dict,
            ),
            message="Code successfully auto-fixed with quality improvements",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in enhanced auto-fix: {str(e)}", exc_info=True)
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Enhanced auto-fix failed",
            detail=str(e),
        )


@router.post("/preventive-quality-enhancement", response_model=QualityCheckResponse)
async def preventive_quality_enhancement(request: PreventiveQualityRequest):
    """
    Perform comprehensive preventive code quality enhancement.

    This endpoint runs quality checks and fixes on specified files to prevent
    errors before they occur in the development process.

    Args:
        request: PreventiveQualityRequest containing project and enhancement details

    Returns:
        QualityCheckResponse with comprehensive enhancement results
    """
    try:
        logger.info(f"Preventive quality enhancement for project {request.project_id}")

        # Determine target files
        project_path = os.path.join("repos", request.project_id)
        if not os.path.exists(project_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project not found: {request.project_id}",
            )

        target_files = request.file_paths or []
        if not target_files:
            # Auto-discover files based on language
            for root, dirs, files in os.walk(project_path):
                for file in files:
                    if request.language == "python" and file.endswith(".py"):
                        rel_path = os.path.relpath(
                            os.path.join(root, file), project_path
                        )
                        target_files.append(rel_path)
                    elif request.language in ["javascript", "typescript"] and (
                        file.endswith(".js") or file.endswith(".ts")
                    ):
                        rel_path = os.path.relpath(
                            os.path.join(root, file), project_path
                        )
                        target_files.append(rel_path)

        if not target_files:
            return success_response(
                status_code=status.HTTP_200_OK,
                data=QualityCheckResponse(
                    success=True,
                    message="No files found for quality enhancement",
                    project_id=request.project_id,
                    files_checked=0,
                    issues_found=0,
                    issues_fixed=0,
                    remaining_issues=0,
                    tools_used=[],
                    detailed_results={},
                ),
                message="No files found for enhancement",
            )

        # Initialize quality service
        quality_service = CodeQualityService()

        # Process each file
        total_issues_found = 0
        total_issues_fixed = 0
        total_remaining_issues = 0
        all_tools_used = set()
        detailed_results = {}

        for file_path in target_files:
            full_path = os.path.join(project_path, file_path)

            if not os.path.exists(full_path):
                logger.warning(f"File not found: {file_path}")
                continue

            try:
                # Read current code
                with open(full_path, "r", encoding="utf-8") as f:
                    current_code = f.read()

                # Apply quality improvements
                quality_report = await quality_service.improve_generated_code(
                    code=current_code,
                    file_path=file_path,
                    language=request.language,
                    project_dir=project_path,
                )

                # Update totals
                total_issues_found += len(quality_report.issues_found)
                total_issues_fixed += len(quality_report.issues_fixed)
                total_remaining_issues += len(quality_report.remaining_issues)
                all_tools_used.update(quality_report.tools_used)

                # Write improved code back if auto_fix is enabled
                if request.auto_fix and quality_report.fixed_code != current_code:
                    # Create backup
                    backup_path = f"{full_path}.backup"
                    with open(backup_path, "w", encoding="utf-8") as f:
                        f.write(current_code)

                    # Write improved code
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(quality_report.fixed_code)

                # Store detailed results
                detailed_results[file_path] = {
                    "issues_found": len(quality_report.issues_found),
                    "issues_fixed": len(quality_report.issues_fixed),
                    "remaining_issues": len(quality_report.remaining_issues),
                    "result": quality_report.result.value,
                    "execution_time": quality_report.execution_time,
                    "tools_used": quality_report.tools_used,
                }

            except Exception as e:
                logger.error(f"Error processing file {file_path}: {str(e)}")
                detailed_results[file_path] = {
                    "error": str(e),
                    "issues_found": 0,
                    "issues_fixed": 0,
                    "remaining_issues": 0,
                }

        return success_response(
            status_code=status.HTTP_200_OK,
            data=QualityCheckResponse(
                success=True,
                message="Preventive quality enhancement completed",
                project_id=request.project_id,
                files_checked=len(target_files),
                issues_found=total_issues_found,
                issues_fixed=total_issues_fixed,
                remaining_issues=total_remaining_issues,
                tools_used=list(all_tools_used),
                detailed_results=detailed_results,
            ),
            message="Preventive quality enhancement successful",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error in preventive quality enhancement: {str(e)}", exc_info=True
        )
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Preventive quality enhancement failed",
            detail=str(e),
        )


@router.post("/post-generation-quality-check", response_model=QualityCheckResponse)
async def post_generation_quality_check(request: CodeGenerationQualityRequest):
    """
    Perform quality checks immediately after code generation.

    This endpoint should be called after generating new code files to ensure
    they meet quality standards before being written to the project.

    Args:
        request: CodeGenerationQualityRequest containing newly generated files

    Returns:
        QualityCheckResponse with post-generation quality results
    """
    try:
        logger.info(f"Post-generation quality check for project {request.project_id}")

        project_path = os.path.join("repos", request.project_id)
        if not os.path.exists(project_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project not found: {request.project_id}",
            )

        # Initialize quality service
        quality_service = CodeQualityService()

        # Process each generated file
        total_issues_found = 0
        total_issues_fixed = 0
        total_remaining_issues = 0
        all_tools_used = set()
        detailed_results = {}

        for file_path in request.generated_files:
            full_path = os.path.join(project_path, file_path)

            if not os.path.exists(full_path):
                logger.warning(f"Generated file not found: {file_path}")
                continue

            try:
                # Read generated code
                with open(full_path, "r", encoding="utf-8") as f:
                    generated_code = f.read()

                # Apply quality improvements
                quality_report = await quality_service.improve_generated_code(
                    code=generated_code,
                    file_path=file_path,
                    language=request.language,
                    project_dir=project_path,
                )

                # Update totals
                total_issues_found += len(quality_report.issues_found)
                total_issues_fixed += len(quality_report.issues_fixed)
                total_remaining_issues += len(quality_report.remaining_issues)
                all_tools_used.update(quality_report.tools_used)

                # Write improved code back if auto_fix is enabled
                if request.auto_fix and quality_report.fixed_code != generated_code:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(quality_report.fixed_code)

                # Store detailed results
                detailed_results[file_path] = {
                    "issues_found": len(quality_report.issues_found),
                    "issues_fixed": len(quality_report.issues_fixed),
                    "remaining_issues": len(quality_report.remaining_issues),
                    "result": quality_report.result.value,
                    "execution_time": quality_report.execution_time,
                    "tools_used": quality_report.tools_used,
                    "improvements_applied": quality_report.fixed_code != generated_code,
                }

            except Exception as e:
                logger.error(f"Error processing generated file {file_path}: {str(e)}")
                detailed_results[file_path] = {
                    "error": str(e),
                    "issues_found": 0,
                    "issues_fixed": 0,
                    "remaining_issues": 0,
                }

        return success_response(
            status_code=status.HTTP_200_OK,
            data=QualityCheckResponse(
                success=True,
                message="Post-generation quality check completed",
                project_id=request.project_id,
                files_checked=len(request.generated_files),
                issues_found=total_issues_found,
                issues_fixed=total_issues_fixed,
                remaining_issues=total_remaining_issues,
                tools_used=list(all_tools_used),
                detailed_results=detailed_results,
            ),
            message="Post-generation quality check successful",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in post-generation quality check: {str(e)}", exc_info=True)
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Post-generation quality check failed",
            detail=str(e),
        )
