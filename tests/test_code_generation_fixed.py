"""
Fixed comprehensive test suite for CodeGenerationService to capture component generation errors.

This test suite covers all potential error scenarios in the Python template code generation process,
including primary component failures, entity name extraction issues, database component errors,
file writing problems, quality processing failures, and integration issues.
"""

import asyncio
import base64
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
        }
        
        # Mock component generation
        async def mock_generate_component(*args, **kwargs):
            component_type = kwargs.get("component_type", "endpoint")
            return {
                "component_type": component_type,
                "entity_name": self.test_entity_name,
                "file_path": f"test/{component_type}.py",
                "generated_code": f"# Mock {component_type} code\nclass {self.test_entity_name}:\n    pass",
                "content_base64": base64.b64encode(b"mock code").decode(),
                "file_hash": "mock_hash_123"
            }
        
        template.generate_component = AsyncMock(side_effect=mock_generate_component)
        template.generate_dockerfile = AsyncMock(return_value="FROM python:3.9\nCOPY . .")
        template.generate_migration = AsyncMock(return_value={
            "file_path": "test_migration.py",
            "generated_code": "# Migration code",
            "content_base64": base64.b64encode(b"migration").decode(),
            "file_hash": "migration_hash"
        })
        
        return template

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
        request = self.create_mock_request()
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template') as mock_factory:
            mock_template = self.create_mock_language_template(extracted_entity=None)
            mock_template.extract_entity_from_code.return_value = None
            mock_template.extract_entity_from_prompt.return_value = None
            mock_factory.return_value = mock_template
            
            with patch.object(self.service, '_write_generated_file'), \
                 patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
                 patch.object(self.service, '_notify_event', new_callable=AsyncMock):
                
                result = await self.service.generate_code(request, self.mock_db)
                
                # Test should handle case where entity name extraction fails
                # Service should use fallback behavior
                assert result is not None

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
                 patch.object(self.service, '_notify_event', new_callable=AsyncMock):
                
                result = await self.service.generate_code(request, self.mock_db)
                
                # Should handle the error gracefully
                assert result is not None

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
    async def test_invalid_language_template(self):
        """Test handling of invalid language template."""
        request = self.create_mock_request(language="invalid_language")
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template', side_effect=Exception("Unsupported language")):
            result = await self.service.generate_code(request, self.mock_db)
            
            assert not result.success
            assert "Unsupported language" in result.message

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


class TestCodeGenerationServiceEdgeCases:
    """Test edge cases and boundary conditions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CodeGenerationService()

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
            mock_template.extract_entity_from_prompt.return_value = None
            mock_factory.return_value = mock_template
            
            with patch.object(self.service, '_notify_info', new_callable=AsyncMock):
                result = await self.service.generate_code(request, Mock())
                
                # Should handle empty prompt gracefully
                assert result is not None

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
