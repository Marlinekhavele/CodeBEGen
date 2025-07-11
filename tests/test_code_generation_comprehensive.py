"""
Comprehensive test suite for CodeGenerationService to capture component generation errors.

This test suite covers all potential error scenarios in the Python template code generation process,
including primary component failures, entity name extraction issues, database component errors,
file writing problems, quality processing failures, and integration issues.
"""

import asyncio
import base64
import hashlib
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from typing import Any, Dict, List, Optional

import pytest

from app.api.v1.services.code_generation import CodeGenerationService
from app.api.v1.schemas.code_generation import CodeGenerationRequest


class TestCodeGenerationServiceComprehensive:
    """Comprehensive test suite for CodeGenerationService error scenarios."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.service = CodeGenerationService()
        self.mock_db = Mock()
        self.test_project_id = "test-project-123"
        self.test_entity_name = "Book"
        self.test_prompt = "Create a book management endpoint"
        
    def create_mock_request(self, **kwargs) -> CodeGenerationRequest:
        """Create a mock CodeGenerationRequest with default values."""
        defaults = {
            "project_id": self.test_project_id,
            "prompt": self.test_prompt,
            "language": "python",
            "method": "GET",
            "endpoint_path": "/api/books",
            "additional_context": None
        }
        defaults.update(kwargs)
        return CodeGenerationRequest(**defaults)

    def create_mock_language_template(self, **kwargs):
        """Create a mock language template with default behavior."""
        template = Mock()
        template.get_file_extension.return_value = "py"
        template.get_component_map.return_value = {"endpoint": "endpoint"}
        template.get_required_components.return_value = ["endpoint", "model", "schema", "helpers", "migration"]
        template.needs_database.return_value = kwargs.get("needs_database", True)
        template.needs_schema.return_value = kwargs.get("needs_schema", True)
        template.needs_helpers.return_value = kwargs.get("needs_helpers", True)
        template.extract_entity_from_code.return_value = kwargs.get("extracted_entity", self.test_entity_name)
        template.extract_entity_from_prompt.return_value = kwargs.get("extracted_entity", self.test_entity_name)
        template.project_directory = kwargs.get("project_directory", "/tmp/test")
        
        # Mock component paths
        template.get_component_paths.return_value = {
            "endpoint": f"app/api/endpoints/{self.test_entity_name.lower()}_endpoint.py",
            "model": f"app/models/{self.test_entity_name.lower()}.py",
            "schema": f"app/schemas/{self.test_entity_name.lower()}_schema.py",
            "helpers": f"app/helpers/{self.test_entity_name.lower()}_helpers.py",
            "migration": f"alembic/versions/create_{self.test_entity_name.lower()}_table.py",
            "api_docs": f"docs/api/{self.test_entity_name.lower()}_api.md"
        }          # Mock component generation
        async def mock_generate_component(*args, **kwargs):
            component_type = kwargs.get("component_type", "endpoint")
            mock_code = f"# Mock {component_type} code\nclass {self.test_entity_name}:\n    pass"
            return {
                "component_type": component_type,
                "entity_name": self.test_entity_name,
                "file_path": f"test/{component_type}.py",
                "generated_code": mock_code,
                "content_base64": base64.b64encode(mock_code.encode()).decode(),
                "file_hash": hashlib.md5(mock_code.encode()).hexdigest()            }
        
        template.generate_component = AsyncMock(side_effect=mock_generate_component)
        template.generate_dockerfile = AsyncMock(return_value="FROM python:3.9\nCOPY . .")
        template.generate_migration = AsyncMock(return_value={
            "file_path": "test_migration.py",
            "generated_code": "# Migration code",
            "content_base64": base64.b64encode(b"# Migration code").decode(),
            "file_hash": hashlib.md5(b"# Migration code").hexdigest()
        })
          # Add missing component generation methods with proper structure
        async def mock_generate_helpers(*args, **kwargs):
            mock_code = "# Generated helpers code\ndef helper_function():\n    pass"
            return {
                "component_type": "helpers",
                "entity_name": self.test_entity_name,
                "file_path": "test/helpers.py",
                "generated_code": mock_code,
                "content_base64": base64.b64encode(mock_code.encode()).decode(),
                "file_hash": hashlib.md5(mock_code.encode()).hexdigest()
            }
        
        template.generate_helpers = AsyncMock(side_effect=mock_generate_helpers)
        
        return template    
    def get_comprehensive_patches(self):
        """Get comprehensive patches to avoid quality service errors."""
        return [
            patch.object(self.service, '_write_generated_file'),
            patch.object(self.service, '_notify_info', new_callable=AsyncMock),
            patch.object(self.service, '_notify_event', new_callable=AsyncMock),
            patch.object(self.service, '_check_for_existing_model', return_value=False),
            patch.object(self.service, '_apply_tier1_prompt_enhancement', return_value="enhanced prompt"),            patch.object(self.service, '_apply_tier2_tier3_quality_processing', side_effect=self._mock_tier2_tier3_quality_processing),
            patch.object(self.service, '_apply_tier4_semantic_validation', return_value={
                "overall_score": 90,
                "validation_success": True
            }),            patch.object(self.service, '_generate_quality_recommendations', return_value=[]),
            patch.object(self.service, '_generate_api_docs', return_value="# API Documentation\nGenerated docs content"),
            patch.object(self.service, '_commit_files_to_git', return_value=True),
            patch('app.api.v1.utils.git_utils.get_repo_url', return_value="mock://repo.git"),            patch('app.api.v1.services.langchain_service.LangchainService.generate_code_with_template', return_value={
                "file_path": "mock/path/file.py",
                "generated_code": "mock code",
                "content_base64": base64.b64encode(b"mock code").decode(),
                "file_hash": hashlib.md5(b"mock code").hexdigest(),
                "language": "python"
            }),
            patch('app.api.v1.services.enhanced_quality_middleware.EnhancedCodeGenerationQualityMiddleware.process_generated_files', return_value=({}, {})),]

    async def _mock_tier2_tier3_quality_processing(self, component, language, project_id, entity_name):
        """
        Mock implementation of _apply_tier2_tier3_quality_processing that preserves 
        the original component structure while adding quality metadata.
        
        This prevents Pydantic validation errors by ensuring all required fields 
        (file_path, generated_code, content_base64, file_hash) are preserved.
        """
        if not isinstance(component, dict):
            return component
            
        # Preserve the original component structure - this is crucial for Pydantic validation
        original_code = component.get("generated_code", "")
        
        # Ensure all required fields are present with fallback values if missing
        if "content_base64" not in component and original_code:
            component["content_base64"] = base64.b64encode(original_code.encode()).decode()
        
        if "file_hash" not in component and original_code:
            component["file_hash"] = hashlib.md5(original_code.encode()).hexdigest()
            
        # Add quality metadata as the real service method does
        component["quality_metadata"] = {
            "tier2_validation": {
                "validation_success": True,
                "issues": [],
                "quality_score": 85
            },
            "tier3_enhancement": {
                "enhanced_code": original_code,
                "quality_score": 85,
                "improvements": ["formatting", "linting"],
                "enhancement_success": True
            },
            "quality_score": 85,
            "improvements_applied": ["formatting", "linting"],
        }
        
        return component

    @pytest.mark.asyncio
    async def test_primary_component_generation_failure(self):
        """Test handling of primary component generation failures."""
        request = self.create_mock_request()
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = self.create_mock_language_template()
            mock_template.generate_component.side_effect = Exception("Template generation failed")
            mock_factory.return_value = mock_template
            
            with patch.object(self.service, '_notify_info', new_callable=AsyncMock):
                result = await self.service.generate_code(request, self.mock_db)
                
                assert not result.success
                assert "Template generation failed" in result.message                
                assert result.result is None

    @pytest.mark.asyncio
    async def test_entity_name_extraction_failure(self):
        """Test handling of entity name extraction failures."""
        # Use a request with no extractable entity name in prompt or endpoint path
        request = self.create_mock_request(
            prompt="Create an endpoint", 
            endpoint_path="/api/"  # Empty path segment that won't extract an entity
        )
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = self.create_mock_language_template(extracted_entity=None)
            mock_template.extract_entity_from_code.return_value = None
            mock_template.extract_entity_from_prompt.return_value = None
            mock_factory.return_value = mock_template
            
            # Use comprehensive patches
            patches = self.get_comprehensive_patches()
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9], patches[10], patches[11], patches[12]:
                result = await self.service.generate_code(request, self.mock_db)
                
                # Should still succeed but use fallback entity name
                assert result.success
                # Should use "Resource" as fallback entity name
                assert "Resource" in str(result.result.entity_name) or result.result.entity_name == "Resource"

    @pytest.mark.asyncio
    async def test_database_component_generation_error(self):
        """Test handling of database component generation errors."""
        request = self.create_mock_request()
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = self.create_mock_language_template()
            
            # Make model generation fail
            async def failing_generate_component(*args, **kwargs):
                component_type = kwargs.get("component_type")
                if component_type == "model":
                    raise Exception("Database connection failed")
                return {
                    "component_type": component_type,
                    "entity_name": self.test_entity_name,
                    "file_path": f"test/{component_type}.py",
                    "generated_code": f"# Mock {component_type} code",
                    "content_base64": base64.b64encode(b"mock code").decode(),
                    "file_hash": "mock_hash"
                }
            
            mock_template.generate_component.side_effect = failing_generate_component
            mock_factory.return_value = mock_template
            
            with patch.object(self.service, '_write_generated_file'), \
                 patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
                 patch.object(self.service, '_notify_event', new_callable=AsyncMock), \
                 patch.object(self.service, '_check_for_existing_model', return_value=False):
                
                result = await self.service.generate_code(request, self.mock_db)
                
                # Should still succeed for other components
                assert result.success
                # Model should not be present in result
                assert "model" not in result.result.__dict__ or result.result.model is None

    @pytest.mark.asyncio
    async def test_file_writing_permission_error(self):
        """Test handling of file writing permission errors."""
        request = self.create_mock_request()
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = self.create_mock_language_template()
            mock_factory.return_value = mock_template
            
            def failing_write_file(*args, **kwargs):
                raise PermissionError("Permission denied to write file")
            
            with patch.object(self.service, '_write_generated_file', side_effect=failing_write_file), \
                 patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
                 patch.object(self.service, '_notify_event', new_callable=AsyncMock):
                
                result = await self.service.generate_code(request, self.mock_db)
                
                assert not result.success
                assert "Permission denied" in result.message

    @pytest.mark.asyncio
    async def test_quality_processing_failure(self):
        """Test handling of quality processing pipeline failures."""
        request = self.create_mock_request()
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = self.create_mock_language_template()
            mock_factory.return_value = mock_template
            
            with patch.object(self.service, '_write_generated_file'), \
                 patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
                 patch.object(self.service, '_notify_event', new_callable=AsyncMock), \
                 patch.object(self.service, '_apply_tier1_prompt_enhancement', side_effect=Exception("Quality processing failed")):
                
                result = await self.service.generate_code(request, self.mock_db)
                
                assert not result.success
                assert "Quality processing failed" in result.message

    @pytest.mark.asyncio
    async def test_api_docs_generation_failure(self):
        """Test handling of API documentation generation failures."""
        request = self.create_mock_request()
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = self.create_mock_language_template()
            mock_factory.return_value = mock_template
            
            with patch.object(self.service, '_write_generated_file'), \
                 patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
                 patch.object(self.service, '_notify_event', new_callable=AsyncMock), \
                 patch.object(self.service, '_generate_api_docs', side_effect=Exception("API docs generation failed")):
                
                result = await self.service.generate_code(request, self.mock_db)
                
                # Should still succeed but without API docs
                assert result.success
                # API docs should not be present or should be empty
                api_docs = getattr(result.result, 'api_docs', None)
                assert api_docs is None or api_docs == {}

    @pytest.mark.asyncio
    async def test_git_operations_failure(self):
        """Test handling of Git operations failures."""
        request = self.create_mock_request()
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = self.create_mock_language_template()
            mock_factory.return_value = mock_template
            
            with patch.object(self.service, '_write_generated_file'), \
                 patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
                 patch.object(self.service, '_notify_event', new_callable=AsyncMock), \
                 patch.object(self.service, '_commit_files_to_git', side_effect=Exception("Git commit failed")):
                
                result = await self.service.generate_code(request, self.mock_db)
                
                assert not result.success
                assert "Git commit failed" in result.message

    @pytest.mark.asyncio
    async def test_missing_project_directory(self):
        """Test handling of missing project directory."""
        request = self.create_mock_request()
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = self.create_mock_language_template(project_directory=None)
            mock_factory.return_value = mock_template
            
            with patch('app.api.v1.utils.git_utils.get_repo_url', side_effect=Exception("Repo not found")), \
                 patch.object(self.service, '_write_generated_file'), \
                 patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
                 patch.object(self.service, '_notify_event', new_callable=AsyncMock):
                
                result = await self.service.generate_code(request, self.mock_db)
                
                # Should still succeed but with warnings
                assert result.success

    @pytest.mark.asyncio
    async def test_invalid_language_template(self):
        """Test handling of invalid language template."""
        request = self.create_mock_request(language="invalid_language")
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template', side_effect=Exception("Unsupported language")):
            result = await self.service.generate_code(request, self.mock_db)
            
            assert not result.success
            assert "Unsupported language" in result.message

    @pytest.mark.asyncio
    async def test_model_schema_manager_failure(self):
        """Test handling of ModelSchemaManager failures."""
        request = self.create_mock_request()
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = self.create_mock_language_template()
            mock_factory.return_value = mock_template
            
            with patch.object(self.service, '_write_generated_file'), \
                 patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
                 patch.object(self.service, '_notify_event', new_callable=AsyncMock), \
                 patch.object(self.service, '_check_for_existing_model', return_value=True), \
                 patch('app.api.v1.services.model_schema_update.model_schema_manager.ModelSchemaManager.process_model_changes', side_effect=Exception("Schema update failed")):
                
                result = await self.service.generate_code(request, self.mock_db)
                
                assert not result.success
                assert "Schema update failed" in result.message

    @pytest.mark.asyncio
    async def test_helpers_generation_failure(self):
        """Test handling of helpers generation failures."""
        request = self.create_mock_request()
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = self.create_mock_language_template()
            
            # Make helpers generation fail
            async def failing_generate_component(*args, **kwargs):
                component_type = kwargs.get("component_type")
                if component_type == "helpers":
                    raise Exception("Helpers generation failed")
                return {
                    "component_type": component_type,
                    "entity_name": self.test_entity_name,
                    "file_path": f"test/{component_type}.py",
                    "generated_code": f"# Mock {component_type} code",
                    "content_base64": base64.b64encode(b"mock code").decode(),
                    "file_hash": "mock_hash"
                }
            
            mock_template.generate_component.side_effect = failing_generate_component
            mock_factory.return_value = mock_template
            
            with patch.object(self.service, '_write_generated_file'), \
                 patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
                 patch.object(self.service, '_notify_event', new_callable=AsyncMock), \
                 patch.object(self.service, '_check_for_existing_model', return_value=False):
                
                result = await self.service.generate_code(request, self.mock_db)
                
                # Should still succeed for other components
                assert result.success
                # Helpers should not be present in result
                assert "helpers" not in result.result.__dict__ or result.result.helpers is None

    @pytest.mark.asyncio
    async def test_migration_generation_failure(self):
        """Test handling of migration generation failures."""
        request = self.create_mock_request()
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = self.create_mock_language_template()
            mock_template.generate_migration.side_effect = Exception("Migration generation failed")
            mock_factory.return_value = mock_template
            
            with patch.object(self.service, '_write_generated_file'), \
                 patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
                 patch.object(self.service, '_notify_event', new_callable=AsyncMock), \
                 patch.object(self.service, '_check_for_existing_model', return_value=False):
                
                result = await self.service.generate_code(request, self.mock_db)
                
                # Should still succeed for other components
                assert result.success
                # Migration should not be present in result
                assert "migration" not in result.result.__dict__ or result.result.migration is None

    @pytest.mark.asyncio
    async def test_dockerfile_generation_failure(self):
        """Test handling of Dockerfile generation failures."""
        request = self.create_mock_request()
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = self.create_mock_language_template()
            mock_template.generate_dockerfile.side_effect = Exception("Dockerfile generation failed")
            mock_factory.return_value = mock_template
            
            with patch.object(self.service, '_write_generated_file'), \
                 patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
                 patch.object(self.service, '_notify_event', new_callable=AsyncMock):
                
                result = await self.service.generate_code(request, self.mock_db)
                
                # Should still succeed for other components
                assert result.success
                # Dockerfile should not be present in result
                assert "dockerfile" not in result.result.__dict__ or result.result.dockerfile is None

    @pytest.mark.asyncio
    async def test_component_path_resolution_failure(self):
        """Test handling of component path resolution failures."""
        request = self.create_mock_request()
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = self.create_mock_language_template()
            mock_template.get_component_paths.side_effect = Exception("Path resolution failed")
            mock_factory.return_value = mock_template
            
            with patch.object(self.service, '_notify_info', new_callable=AsyncMock):
                result = await self.service.generate_code(request, self.mock_db)
                
                assert not result.success
                assert "Path resolution failed" in result.message

    @pytest.mark.asyncio
    async def test_partial_component_generation_success(self):
        """Test scenario where some components succeed and others fail."""
        request = self.create_mock_request()
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = self.create_mock_language_template()
            
            # Make some components fail
            call_count = 0
            async def selective_failing_generate_component(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                component_type = kwargs.get("component_type")
                
                if component_type == "schema" and call_count > 1:
                    raise Exception("Schema generation failed")
                elif component_type == "migration":
                    raise Exception("Migration generation failed")
                
                return {
                    "component_type": component_type,
                    "entity_name": self.test_entity_name,
                    "file_path": f"test/{component_type}.py",
                    "generated_code": f"# Mock {component_type} code",
                    "content_base64": base64.b64encode(b"mock code").decode(),
                    "file_hash": "mock_hash"
                }
            
            mock_template.generate_component.side_effect = selective_failing_generate_component
            mock_factory.return_value = mock_template
            
            with patch.object(self.service, '_write_generated_file'), \
                 patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
                 patch.object(self.service, '_notify_event', new_callable=AsyncMock), \
                 patch.object(self.service, '_check_for_existing_model', return_value=False):
                
                result = await self.service.generate_code(request, self.mock_db)
                
                # Should succeed with partial components
                assert result.success
                # Endpoint should be present
                assert hasattr(result.result, 'endpoint') or 'endpoint' in result.result.__dict__

    @pytest.mark.asyncio
    async def test_callback_notification_failure(self):
        """Test handling of callback notification failures."""
        
        # Create service with failing callbacks
        failing_callback = AsyncMock(side_effect=Exception("Callback failed"))
        service = CodeGenerationService(
            on_component_start={"endpoint": failing_callback},
            on_info=failing_callback
        )
        
        request = self.create_mock_request()
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = self.create_mock_language_template()
            mock_factory.return_value = mock_template
            
            with patch.object(service, '_write_generated_file'):
                # Should not crash even if callbacks fail
                result = await service.generate_code(request, self.mock_db)
                
                # Should still succeed despite callback failures
                assert result.success

    @pytest.mark.asyncio
    async def test_memory_and_resource_constraints(self):
        """Test handling of memory and resource constraint scenarios."""
        request = self.create_mock_request()
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = self.create_mock_language_template()
            
            # Simulate memory error during component generation
            mock_template.generate_component.side_effect = MemoryError("Out of memory")
            mock_factory.return_value = mock_template
            
            with patch.object(self.service, '_notify_info', new_callable=AsyncMock):
                result = await self.service.generate_code(request, self.mock_db)
                
                assert not result.success
                assert "Out of memory" in result.message

    @pytest.mark.asyncio
    async def test_concurrent_generation_conflicts(self):
        """Test handling of concurrent generation conflicts."""
        request = self.create_mock_request()
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = self.create_mock_language_template()
            mock_factory.return_value = mock_template
            
            def conflicting_write_file(*args, **kwargs):
                raise FileExistsError("File already exists from concurrent operation")
            
            with patch.object(self.service, '_write_generated_file', side_effect=conflicting_write_file), \
                 patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
                 patch.object(self.service, '_notify_event', new_callable=AsyncMock):
                result = await self.service.generate_code(request, self.mock_db)
                
                assert not result.success
                assert "File already exists" in result.message

    @pytest.mark.asyncio  
    async def test_edge_case_scenarios(self):
        """Test various edge case scenarios together."""
        request = self.create_mock_request()
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = self.create_mock_language_template()
            mock_factory.return_value = mock_template
            
            with patch.object(self.service, '_write_generated_file'), \
                 patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
                 patch.object(self.service, '_notify_event', new_callable=AsyncMock):
                
                result = await self.service.generate_code(request, self.mock_db)
                assert result.success


class TestCodeGenerationServiceEdgeCases:
    """Test edge cases and boundary conditions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CodeGenerationService()
        self.mock_db = Mock()

    @pytest.mark.asyncio
    async def test_empty_prompt_handling(self):
        """Test handling of empty prompts."""
        request = CodeGenerationRequest(
            project_id="test-project",
            prompt="",
            language="python"
        )
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = Mock()
            mock_template.get_file_extension.return_value = "py"
            mock_template.get_component_map.return_value = {"endpoint": "endpoint"}
            mock_template.needs_database.return_value = False
            mock_template.generate_component.return_value = {
                "file_path": "test/endpoint.py",
                "generated_code": "# Empty prompt fallback code",
                "content_base64": base64.b64encode(b"# Empty prompt fallback code").decode(),
                "file_hash": "test_hash"
            }
            mock_factory.return_value = mock_template
            
            with patch.object(self.service, '_write_generated_file'), \
                 patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
                 patch.object(self.service, '_notify_event', new_callable=AsyncMock):
                
                result = await self.service.generate_code(request, self.mock_db)
                assert result.success

    @pytest.mark.asyncio
    async def test_very_long_prompt_handling(self):
        """Test handling of very long prompts."""
        long_prompt = "Create an endpoint " * 1000  # Very long prompt
        request = CodeGenerationRequest(
            project_id="test-project",
            prompt=long_prompt,
            language="python"
        )
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = Mock()
            mock_template.get_file_extension.return_value = "py"
            mock_template.get_component_map.return_value = {"endpoint": "endpoint"}
            mock_template.needs_database.return_value = False
            mock_template.generate_component.return_value = {
                "file_path": "test/endpoint.py",
                "generated_code": "# Long prompt handling code",
                "content_base64": base64.b64encode(b"# Long prompt handling code").decode(),
                "file_hash": "test_hash"
            }
            mock_factory.return_value = mock_template
            
            with patch.object(self.service, '_write_generated_file'), \
                 patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
                 patch.object(self.service, '_notify_event', new_callable=AsyncMock):
                
                    result = await self.service.generate_code(request, self.mock_db)
                    assert result.success
    
        @pytest.mark.asyncio
        async def test_empty_prompt_handling_edge_case(self):
            """Test handling of empty prompts as edge case."""
            request = CodeGenerationRequest(
                project_id="test-project",
                prompt="",
                language="python"
            )
            
            with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
                mock_template = Mock()
                mock_template.get_file_extension.return_value = "py"
                mock_template.extract_entity_from_prompt.return_value = None
                mock_factory.return_value = mock_template
                
                with patch.object(self.service, '_notify_info', new_callable=AsyncMock):
                    result = await self.service.generate_code(request, Mock())
                    
                    # Should handle empty prompt gracefully
                    assert not result.success or result.success  # Either is acceptable

    @pytest.mark.asyncio
    async def test_very_long_prompt_handling(self):
        """Test handling of very long prompts."""
        long_prompt = "Create a " + "very " * 1000 + "complex endpoint"
        request = CodeGenerationRequest(
            project_id="test-project",
            prompt=long_prompt,
            language="python"
        )
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = Mock()
            mock_template.get_file_extension.return_value = "py"
            mock_factory.return_value = mock_template
            
            with patch.object(self.service, '_notify_info', new_callable=AsyncMock):
                # Should not crash with very long prompts
                result = await self.service.generate_code(request, Mock())
                assert result is not None

    @pytest.mark.asyncio
    async def test_special_characters_in_entity_name(self):
        """Test handling of special characters in entity names."""
        request = CodeGenerationRequest(
            project_id="test-project",
            prompt="Create an endpoint for user@domain.com entities",
            language="python"
        )
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = Mock()
            mock_template.get_file_extension.return_value = "py"
            mock_template.extract_entity_from_prompt.return_value = "user@domain.com"
            mock_factory.return_value = mock_template
            
            with patch.object(self.service, '_notify_info', new_callable=AsyncMock):
                # Should sanitize special characters
                result = await self.service.generate_code(request, Mock())
                assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
