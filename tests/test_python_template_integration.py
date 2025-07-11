"""
Python Template Integration Tests for CodeGenerationService.

This test suite focuses specifically on testing the Python template integration
and catching errors related to Python-specific code generation patterns.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch, mock_open
from typing import Any, Dict, List, Optional

import pytest

from app.api.v1.services.code_generation import CodeGenerationService
from app.api.v1.schemas.code_generation import CodeGenerationRequest


class TestPythonTemplateIntegration:
    """Test Python template specific integration scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CodeGenerationService()
        self.test_project_id = "python-test-project"
        
    @pytest.mark.asyncio
    async def test_python_syntax_validation_error(self):
        """Test handling of Python syntax errors in generated code."""
        request = CodeGenerationRequest(
            project_id=self.test_project_id,
            prompt="Create a book endpoint",
            language="python"
        )
        
        # Mock template that generates invalid Python syntax
        mock_template = Mock()
        mock_template.get_file_extension.return_value = "py"
        mock_template.get_component_map.return_value = {"endpoint": "endpoint"}
        mock_template.get_required_components.return_value = ["endpoint", "model"]
        mock_template.needs_database.return_value = True
        mock_template.extract_entity_from_code.return_value = "Book"
        mock_template.get_component_paths.return_value = {
            "endpoint": "app/endpoints/book_endpoint.py",
            "model": "app/models/book.py"
        }
        
        # Generate invalid Python code
        async def generate_invalid_python(*args, **kwargs):
            return {
                "component_type": "endpoint",
                "entity_name": "Book",
                "file_path": "app/endpoints/book_endpoint.py",
                "generated_code": "def invalid_function(\n    # Missing closing parenthesis and colon",
                "content_base64": "invalid_base64",
                "file_hash": "invalid_hash"
            }
        
        mock_template.generate_component = AsyncMock(side_effect=generate_invalid_python)
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template', return_value=mock_template), \
             patch.object(self.service, '_write_generated_file'), \
             patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
             patch.object(self.service, '_notify_event', new_callable=AsyncMock), \
             patch.object(self.service, '_apply_tier1_prompt_enhancement', return_value="enhanced prompt"), \
             patch.object(self.service, '_apply_tier2_tier3_quality_processing', side_effect=lambda x, *args: x), \
             patch.object(self.service, '_apply_tier4_semantic_validation', return_value={"overall_score": 50}), \
             patch.object(self.service, '_commit_files_to_git', return_value={"success": True}):
            
            result = await self.service.generate_code(request, Mock())
            
            # Should handle syntax errors gracefully
            assert result.success or "syntax" in result.message.lower()

    @pytest.mark.asyncio 
    async def test_python_import_resolution_failure(self):
        """Test handling of Python import resolution failures."""
        request = CodeGenerationRequest(
            project_id=self.test_project_id,
            prompt="Create an endpoint using non-existent imports",
            language="python"
        )
        
        mock_template = Mock()
        mock_template.get_file_extension.return_value = "py"
        mock_template.get_component_map.return_value = {"endpoint": "endpoint"}
        mock_template.get_required_components.return_value = ["endpoint"]
        mock_template.needs_database.return_value = False
        mock_template.extract_entity_from_code.return_value = "Test"
        mock_template.get_component_paths.return_value = {
            "endpoint": "app/endpoints/test_endpoint.py"
        }
        
        # Generate code with non-existent imports
        async def generate_bad_imports(*args, **kwargs):
            return {
                "component_type": "endpoint",
                "entity_name": "Test",
                "file_path": "app/endpoints/test_endpoint.py",
                "generated_code": """
from non_existent_module import NonExistentClass
from another.missing.module import MissingFunction

def test_endpoint():
    return NonExistentClass()
""",
                "content_base64": "test_base64",
                "file_hash": "test_hash"
            }
        
        mock_template.generate_component = AsyncMock(side_effect=generate_bad_imports)
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template', return_value=mock_template), \
             patch.object(self.service, '_write_generated_file'), \
             patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
             patch.object(self.service, '_notify_event', new_callable=AsyncMock), \
             patch.object(self.service, '_apply_tier1_prompt_enhancement', return_value="enhanced prompt"), \
             patch.object(self.service, '_apply_tier2_tier3_quality_processing', side_effect=lambda x, *args: x), \
             patch.object(self.service, '_apply_tier4_semantic_validation', return_value={"overall_score": 30}), \
             patch.object(self.service, '_commit_files_to_git', return_value={"success": True}):
            
            result = await self.service.generate_code(request, Mock())
            
            # Should still generate code but may have quality issues
            assert result.success

    @pytest.mark.asyncio
    async def test_python_database_model_relationship_errors(self):
        """Test handling of SQLAlchemy relationship definition errors."""
        request = CodeGenerationRequest(
            project_id=self.test_project_id,
            prompt="Create a book with author relationship",
            language="python"
        )
        
        mock_template = Mock()
        mock_template.get_file_extension.return_value = "py"
        mock_template.get_component_map.return_value = {"endpoint": "endpoint"}
        mock_template.get_required_components.return_value = ["endpoint", "model"]
        mock_template.needs_database.return_value = True
        mock_template.extract_entity_from_code.return_value = "Book"
        mock_template.get_component_paths.return_value = {
            "endpoint": "app/endpoints/book_endpoint.py",
            "model": "app/models/book.py"
        }
        
        call_count = 0
        async def generate_components(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            component_type = kwargs.get("component_type", "endpoint")
            
            if component_type == "model":
                # Generate model with invalid relationship
                return {
                    "component_type": "model",
                    "entity_name": "Book",
                    "file_path": "app/models/book.py",
                    "generated_code": """
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

class Book(Base):
    __tablename__ = 'books'
    
    id = Column(Integer, primary_key=True)
    title = Column(String)
    # Invalid relationship definition
    author = relationship("NonExistentAuthor", back_populates="non_existent_field")
""",
                    "content_base64": "model_base64",
                    "file_hash": "model_hash"
                }
            else:
                return {
                    "component_type": component_type,
                    "entity_name": "Book", 
                    "file_path": f"app/{component_type}/book.py",
                    "generated_code": f"# {component_type} code",
                    "content_base64": "base64",
                    "file_hash": "hash"
                }
        
        mock_template.generate_component = AsyncMock(side_effect=generate_components)
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template', return_value=mock_template), \
             patch.object(self.service, '_write_generated_file'), \
             patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
             patch.object(self.service, '_notify_event', new_callable=AsyncMock), \
             patch.object(self.service, '_check_for_existing_model', return_value=False), \
             patch.object(self.service, '_apply_tier1_prompt_enhancement', return_value="enhanced prompt"), \
             patch.object(self.service, '_apply_tier2_tier3_quality_processing', side_effect=lambda x, *args: x), \
             patch.object(self.service, '_apply_tier4_semantic_validation', return_value={"overall_score": 40}), \
             patch.object(self.service, '_commit_files_to_git', return_value={"success": True}):
            
            result = await self.service.generate_code(request, Mock())
            
            # Should still succeed but with quality warnings
            assert result.success

    @pytest.mark.asyncio
    async def test_python_pydantic_schema_validation_errors(self):
        """Test handling of Pydantic schema validation errors."""
        request = CodeGenerationRequest(
            project_id=self.test_project_id,
            prompt="Create a user schema with validation",
            language="python"
        )
        
        mock_template = Mock()
        mock_template.get_file_extension.return_value = "py"
        mock_template.get_component_map.return_value = {"endpoint": "endpoint"}
        mock_template.get_required_components.return_value = ["endpoint", "schema"]
        mock_template.needs_database.return_value = False
        mock_template.needs_schema.return_value = True
        mock_template.extract_entity_from_code.return_value = "User"
        mock_template.get_component_paths.return_value = {
            "endpoint": "app/endpoints/user_endpoint.py",
            "schema": "app/schemas/user_schema.py"
        }
        
        async def generate_components(*args, **kwargs):
            component_type = kwargs.get("component_type", "endpoint")
            
            if component_type == "schema":
                # Generate schema with invalid Pydantic definitions
                return {
                    "component_type": "schema",
                    "entity_name": "User",
                    "file_path": "app/schemas/user_schema.py",
                    "generated_code": """
from pydantic import BaseModel, validator

class UserSchema(BaseModel):
    email: str
    age: int
    
    # Invalid validator syntax
    @validator('email', invalid_parameter=True)
    def validate_email(cls, v):
        # Missing validation logic
        pass
        
    # Circular reference
    friend: 'UserSchema' = None
""",
                    "content_base64": "schema_base64",
                    "file_hash": "schema_hash"
                }
            else:
                return {
                    "component_type": component_type,
                    "entity_name": "User",
                    "file_path": f"app/{component_type}/user.py",
                    "generated_code": f"# {component_type} code",
                    "content_base64": "base64",
                    "file_hash": "hash"
                }
        
        mock_template.generate_component = AsyncMock(side_effect=generate_components)
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template', return_value=mock_template), \
             patch.object(self.service, '_write_generated_file'), \
             patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
             patch.object(self.service, '_notify_event', new_callable=AsyncMock), \
             patch.object(self.service, '_apply_tier1_prompt_enhancement', return_value="enhanced prompt"), \
             patch.object(self.service, '_apply_tier2_tier3_quality_processing', side_effect=lambda x, *args: x), \
             patch.object(self.service, '_apply_tier4_semantic_validation', return_value={"overall_score": 35}), \
             patch.object(self.service, '_commit_files_to_git', return_value={"success": True}):
            
            result = await self.service.generate_code(request, Mock())
            
            # Should handle schema validation errors
            assert result.success

    @pytest.mark.asyncio
    async def test_python_fastapi_dependency_injection_errors(self):
        """Test handling of FastAPI dependency injection errors."""
        request = CodeGenerationRequest(
            project_id=self.test_project_id,
            prompt="Create an endpoint with database dependency",
            language="python"
        )
        
        mock_template = Mock()
        mock_template.get_file_extension.return_value = "py"
        mock_template.get_component_map.return_value = {"endpoint": "endpoint"}
        mock_template.get_required_components.return_value = ["endpoint"]
        mock_template.needs_database.return_value = True
        mock_template.extract_entity_from_code.return_value = "Item"
        mock_template.get_component_paths.return_value = {
            "endpoint": "app/endpoints/item_endpoint.py"
        }
        
        async def generate_bad_dependencies(*args, **kwargs):
            return {
                "component_type": "endpoint",
                "entity_name": "Item",
                "file_path": "app/endpoints/item_endpoint.py",
                "generated_code": """
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter()

# Invalid dependency syntax
@router.get("/items")
def get_items(
    db: Session = Depends(non_existent_function),  # Missing function
    invalid_param = Depends(),  # No dependency provided
):
    # Missing return statement
    pass
""",
                "content_base64": "endpoint_base64",
                "file_hash": "endpoint_hash"
            }
        
        mock_template.generate_component = AsyncMock(side_effect=generate_bad_dependencies)
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template', return_value=mock_template), \
             patch.object(self.service, '_write_generated_file'), \
             patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
             patch.object(self.service, '_notify_event', new_callable=AsyncMock), \
             patch.object(self.service, '_apply_tier1_prompt_enhancement', return_value="enhanced prompt"), \
             patch.object(self.service, '_apply_tier2_tier3_quality_processing', side_effect=lambda x, *args: x), \
             patch.object(self.service, '_apply_tier4_semantic_validation', return_value={"overall_score": 25}), \
             patch.object(self.service, '_commit_files_to_git', return_value={"success": True}):
            
            result = await self.service.generate_code(request, Mock())
            
            # Should still succeed but with quality issues
            assert result.success

    @pytest.mark.asyncio
    async def test_python_alembic_migration_errors(self):
        """Test handling of Alembic migration generation errors."""
        request = CodeGenerationRequest(
            project_id=self.test_project_id,
            prompt="Create a complex model with migration",
            language="python"
        )
        
        mock_template = Mock()
        mock_template.get_file_extension.return_value = "py"
        mock_template.get_component_map.return_value = {"endpoint": "endpoint"}
        mock_template.get_required_components.return_value = ["endpoint", "model", "migration"]
        mock_template.needs_database.return_value = True
        mock_template.extract_entity_from_code.return_value = "Product"
        mock_template.get_component_paths.return_value = {
            "endpoint": "app/endpoints/product_endpoint.py",
            "model": "app/models/product.py",
            "migration": "alembic/versions/create_product_table.py"
        }
        
        # Make migration generation fail
        mock_template.generate_migration = AsyncMock(side_effect=Exception("Alembic migration failed"))
        
        async def generate_components(*args, **kwargs):
            component_type = kwargs.get("component_type", "endpoint")
            return {
                "component_type": component_type,
                "entity_name": "Product",
                "file_path": f"app/{component_type}/product.py",
                "generated_code": f"# {component_type} code",
                "content_base64": "base64",
                "file_hash": "hash"
            }
        
        mock_template.generate_component = AsyncMock(side_effect=generate_components)
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template', return_value=mock_template), \
             patch.object(self.service, '_write_generated_file'), \
             patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
             patch.object(self.service, '_notify_event', new_callable=AsyncMock), \
             patch.object(self.service, '_check_for_existing_model', return_value=False), \
             patch.object(self.service, '_apply_tier1_prompt_enhancement', return_value="enhanced prompt"), \
             patch.object(self.service, '_apply_tier2_tier3_quality_processing', side_effect=lambda x, *args: x), \
             patch.object(self.service, '_apply_tier4_semantic_validation', return_value={"overall_score": 60}), \
             patch.object(self.service, '_commit_files_to_git', return_value={"success": True}):
            
            result = await self.service.generate_code(request, Mock())
            
            # Should succeed for other components despite migration failure
            assert result.success

    @pytest.mark.asyncio
    async def test_python_code_formatting_and_linting_errors(self):
        """Test handling of Python code formatting and linting errors."""
        request = CodeGenerationRequest(
            project_id=self.test_project_id,
            prompt="Create poorly formatted code",
            language="python"
        )
        
        mock_template = Mock()
        mock_template.get_file_extension.return_value = "py"
        mock_template.get_component_map.return_value = {"endpoint": "endpoint"}
        mock_template.get_required_components.return_value = ["endpoint"]
        mock_template.needs_database.return_value = False
        mock_template.extract_entity_from_code.return_value = "Test"
        mock_template.get_component_paths.return_value = {
            "endpoint": "app/endpoints/test_endpoint.py"
        }
        
        async def generate_poorly_formatted_code(*args, **kwargs):
            return {
                "component_type": "endpoint",
                "entity_name": "Test",
                "file_path": "app/endpoints/test_endpoint.py",
                "generated_code": """
# Poorly formatted Python code
from fastapi import APIRouter
import os,sys,json,time
router=APIRouter()

def    badly_formatted_function(   param1,param2   ):
    x=1+2+3+4+5
    if x>5:
        y=x*2
        return{"result":y}
    else:
       return None

@router.get("/test")
def test_endpoint():
    result=badly_formatted_function(1,2)
    return result
""",
                "content_base64": "formatted_base64", 
                "file_hash": "formatted_hash"
            }
        
        mock_template.generate_component = AsyncMock(side_effect=generate_poorly_formatted_code)
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template', return_value=mock_template), \
             patch.object(self.service, '_write_generated_file'), \
             patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
             patch.object(self.service, '_notify_event', new_callable=AsyncMock), \
             patch.object(self.service, '_apply_tier1_prompt_enhancement', return_value="enhanced prompt"), \
             patch.object(self.service, '_apply_tier2_tier3_quality_processing', side_effect=lambda x, *args: x), \
             patch.object(self.service, '_apply_tier4_semantic_validation', return_value={"overall_score": 45}), \
             patch.object(self.service, '_commit_files_to_git', return_value={"success": True}):
            
            result = await self.service.generate_code(request, Mock())
            
            # Should succeed but may trigger formatting/linting warnings
            assert result.success

    @pytest.mark.asyncio
    async def test_python_type_annotation_errors(self):
        """Test handling of Python type annotation errors."""
        request = CodeGenerationRequest(
            project_id=self.test_project_id,
            prompt="Create endpoint with type annotations",
            language="python"
        )
        
        mock_template = Mock()
        mock_template.get_file_extension.return_value = "py"
        mock_template.get_component_map.return_value = {"endpoint": "endpoint"}
        mock_template.get_required_components.return_value = ["endpoint"]
        mock_template.needs_database.return_value = False
        mock_template.extract_entity_from_code.return_value = "Typed"
        mock_template.get_component_paths.return_value = {
            "endpoint": "app/endpoints/typed_endpoint.py"
        }
        
        async def generate_bad_types(*args, **kwargs):
            return {
                "component_type": "endpoint",
                "entity_name": "Typed",
                "file_path": "app/endpoints/typed_endpoint.py",
                "generated_code": """
from typing import List, Dict, Optional, Union
from fastapi import APIRouter

router = APIRouter()

# Invalid type annotations
def bad_function(
    param1: NonExistentType,  # Type doesn't exist
    param2: List[Dict[str, Optional[Union[int, str, ComplexType]]]],  # Complex but invalid
    param3: "ForwardRef"  # Forward reference that doesn't exist
) -> Dict[str, List[Optional[AnotherMissingType]]]:
    return {}

@router.get("/typed")
def typed_endpoint() -> InvalidReturnType:
    return bad_function(None, [], "")
""",
                "content_base64": "typed_base64",
                "file_hash": "typed_hash"
            }
        
        mock_template.generate_component = AsyncMock(side_effect=generate_bad_types)
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template', return_value=mock_template), \
             patch.object(self.service, '_write_generated_file'), \
             patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
             patch.object(self.service, '_notify_event', new_callable=AsyncMock), \
             patch.object(self.service, '_apply_tier1_prompt_enhancement', return_value="enhanced prompt"), \
             patch.object(self.service, '_apply_tier2_tier3_quality_processing', side_effect=lambda x, *args: x), \
             patch.object(self.service, '_apply_tier4_semantic_validation', return_value={"overall_score": 30}), \
             patch.object(self.service, '_commit_files_to_git', return_value={"success": True}):
            
            result = await self.service.generate_code(request, Mock())
            
            # Should handle type annotation errors
            assert result.success

    @pytest.mark.asyncio
    async def test_python_async_await_errors(self):
        """Test handling of async/await pattern errors."""
        request = CodeGenerationRequest(
            project_id=self.test_project_id,
            prompt="Create async endpoint with database operations",
            language="python"
        )
        
        mock_template = Mock()
        mock_template.get_file_extension.return_value = "py"
        mock_template.get_component_map.return_value = {"endpoint": "endpoint"}
        mock_template.get_required_components.return_value = ["endpoint"]
        mock_template.needs_database.return_value = True
        mock_template.extract_entity_from_code.return_value = "Async"
        mock_template.get_component_paths.return_value = {
            "endpoint": "app/endpoints/async_endpoint.py"
        }
        
        async def generate_bad_async(*args, **kwargs):
            return {
                "component_type": "endpoint",
                "entity_name": "Async",
                "file_path": "app/endpoints/async_endpoint.py",
                "generated_code": """
from fastapi import APIRouter
import asyncio

router = APIRouter()

# Bad async patterns
def sync_function():
    # Using await in sync function
    result = await asyncio.sleep(1)  # Error: await in non-async function
    return result

async def async_function():
    # Missing await
    result = asyncio.sleep(1)  # Should be: await asyncio.sleep(1)
    # Calling sync function that uses await incorrectly
    return sync_function()

@router.get("/async")
def sync_endpoint():
    # Can't call async function from sync without proper handling
    return async_function()  # Error: missing await or asyncio.run
""",
                "content_base64": "async_base64",
                "file_hash": "async_hash"
            }
        
        mock_template.generate_component = AsyncMock(side_effect=generate_bad_async)
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template', return_value=mock_template), \
             patch.object(self.service, '_write_generated_file'), \
             patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
             patch.object(self.service, '_notify_event', new_callable=AsyncMock), \
             patch.object(self.service, '_apply_tier1_prompt_enhancement', return_value="enhanced prompt"), \
             patch.object(self.service, '_apply_tier2_tier3_quality_processing', side_effect=lambda x, *args: x), \
             patch.object(self.service, '_apply_tier4_semantic_validation', return_value={"overall_score": 20}), \
             patch.object(self.service, '_commit_files_to_git', return_value={"success": True}):
            
            result = await self.service.generate_code(request, Mock())
            
            # Should handle async/await errors
            assert result.success

    @pytest.mark.asyncio
    async def test_python_virtual_environment_path_issues(self):
        """Test handling of virtual environment and path issues."""
        request = CodeGenerationRequest(
            project_id=self.test_project_id,
            prompt="Create endpoint in virtual environment",
            language="python"
        )
        
        mock_template = Mock()
        mock_template.get_file_extension.return_value = "py"
        mock_template.get_component_map.return_value = {"endpoint": "endpoint"}
        mock_template.get_required_components.return_value = ["endpoint"]
        mock_template.needs_database.return_value = False
        mock_template.extract_entity_from_code.return_value = "Env"
        mock_template.project_directory = "/non/existent/venv/path"
        mock_template.get_component_paths.return_value = {
            "endpoint": "/non/existent/venv/path/app/endpoints/env_endpoint.py"
        }
        
        async def generate_with_path_issues(*args, **kwargs):
            return {
                "component_type": "endpoint",
                "entity_name": "Env",
                "file_path": "/non/existent/venv/path/app/endpoints/env_endpoint.py",
                "generated_code": "# Endpoint code",
                "content_base64": "env_base64",
                "file_hash": "env_hash"
            }
        
        mock_template.generate_component = AsyncMock(side_effect=generate_with_path_issues)
        
        # Mock file writing to raise permission error
        def failing_file_write(*args, **kwargs):
            raise PermissionError("Cannot write to virtual environment path")
        
        with patch('app.api.v1.services.language_templates.LanguageTemplateFactory.get_template', return_value=mock_template), \
             patch.object(self.service, '_write_generated_file', side_effect=failing_file_write), \
             patch.object(self.service, '_notify_info', new_callable=AsyncMock), \
             patch.object(self.service, '_notify_event', new_callable=AsyncMock):
            
            result = await self.service.generate_code(request, Mock())
            
            # Should handle path/permission errors
            assert not result.success
            assert "Permission" in result.message or "path" in result.message.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
