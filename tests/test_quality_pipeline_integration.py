"""
Integration Test for Quality Pipeline System

This test verifies that the complete 4-tier quality assurance pipeline
is working correctly with the FastAPI application.
"""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.v1.services.quality_config_manager import (
    QualityConfigLevel,
    QualityConfigManager,
)
from app.api.v1.services.quality_pipeline_orchestrator import (
    QualityAssurancePipeline,
    QualityLevel,
)

# We'll import from the main application
from main import app


class TestQualityPipelineIntegration:
    """Integration tests for the quality pipeline system"""

    @pytest.fixture
    def client(self):
        """Create a test client"""
        return TestClient(app)

    @pytest.fixture
    def pipeline(self):
        """Create a quality pipeline instance"""
        return QualityAssurancePipeline()

    @pytest.fixture
    def config_manager(self):
        """Create a config manager instance"""
        return QualityConfigManager()

    @pytest.fixture
    def sample_python_code(self):
        """Sample Python code with various quality issues"""
        return """
import os
import sys
import unused_module

def function_with_issues():
    # Undefined variable
    result = undefined_var + 5

    # SQL injection vulnerability
    query = "SELECT * FROM users WHERE id = %s" % user_id

    # Unused variable
    unused_var = "not used"

    # Missing return
    if True:
        print("Hello")
    # No return statement

# Missing function docstring
def another_function(param1, param2, param3, param4, param5, param6, param7):
    # Too many parameters (complexity issue)
    if param1:
        if param2:
            if param3:
                if param4:
                    if param5:
                        return param6 + param7
    return None
"""

    def test_api_endpoints_registration(self, client):
        """Test that quality pipeline API endpoints are properly registered"""
        # Test configuration endpoints
        response = client.get("/api/v1/quality/config")
        assert response.status_code in [200, 422]  # Should be accessible

        response = client.get("/api/v1/quality/health")
        assert response.status_code == 200

        # Test that the endpoints are in the OpenAPI schema
        response = client.get("/openapi.json")
        assert response.status_code == 200
        openapi_data = response.json()

        # Check for quality endpoints in the schema
        paths = openapi_data.get("paths", {})
        quality_endpoints = [path for path in paths.keys() if "/quality/" in path]
        assert len(quality_endpoints) > 0, "Quality endpoints should be registered"

    def test_quality_config_manager(self, config_manager):
        """Test quality configuration management"""
        # Test getting default configuration
        config = config_manager.get_config("python", QualityConfigLevel.STANDARD)
        assert config is not None
        assert config.language == "python"
        assert config.level == QualityConfigLevel.STANDARD

        # Test configuration validation
        assert "enable_prompt_enhancement" in config.settings
        assert "enable_real_time_validation" in config.settings
        assert "enable_code_quality" in config.settings
        assert "enable_semantic_validation" in config.settings

    def test_pipeline_initialization(self, pipeline):
        """Test that the quality pipeline initializes correctly"""
        assert pipeline is not None
        assert hasattr(pipeline, "prompt_service")
        assert hasattr(pipeline, "validation_service")
        assert hasattr(pipeline, "quality_service")
        assert hasattr(pipeline, "semantic_service")

    @pytest.mark.asyncio
    async def test_pipeline_basic_execution(self, pipeline, sample_python_code):
        """Test basic pipeline execution"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(sample_python_code)
            f.flush()
            temp_file_path = f.name

        try:
            # Test pipeline execution
            result = await pipeline.run_pipeline(
                code=sample_python_code,
                language="python",
                file_path=temp_file_path,
                quality_level=QualityLevel.STANDARD,
            )

            # Verify results structure
            assert result is not None
            assert "tier1_result" in result
            assert "tier2_result" in result
            assert "tier3_result" in result
            assert "tier4_result" in result
            assert "pipeline_summary" in result

            # Check that issues were detected
            summary = result["pipeline_summary"]
            assert "total_issues_found" in summary
            assert "total_issues_fixed" in summary

        finally:
            # Cleanup - file is now closed so we can delete it
            try:
                Path(temp_file_path).unlink(missing_ok=True)
            except PermissionError:
                # On Windows, sometimes need to wait a bit
                import time

                time.sleep(0.1)
                try:
                    Path(temp_file_path).unlink(missing_ok=True)
                except PermissionError:
                    pass  # Ignore if still can't delete

    def test_error_pattern_database_integration(self):
        """Test that the error pattern database is accessible"""
        from app.api.v1.services.error_pattern_database import get_error_database

        db = get_error_database()
        assert db is not None

        # Test getting patterns by language
        python_patterns = db.get_patterns_by_language("python")
        assert len(python_patterns) > 0

        # Test pattern structure
        pattern = python_patterns[0]
        assert hasattr(pattern, "id")
        assert hasattr(pattern, "name")
        assert hasattr(pattern, "category")
        assert hasattr(pattern, "severity")
        assert hasattr(pattern, "solution")

    @pytest.mark.asyncio
    async def test_api_quality_analysis_endpoint(self, client, sample_python_code):
        """Test the quality analysis API endpoint"""
        payload = {
            "code": sample_python_code,
            "language": "python",
            "quality_level": "STANDARD",
        }

        response = client.post("/api/v1/quality/analyze", json=payload)

        # Should succeed or return validation error (not 500)
        assert response.status_code in [
            200,
            422,
        ], f"Unexpected status: {response.status_code}"

        if response.status_code == 200:
            result = response.json()
            assert "analysis_id" in result or "results" in result

    def test_configuration_api_endpoints(self, client):
        """Test configuration management API endpoints"""
        # Test getting available configurations
        response = client.get("/api/v1/quality/config/languages")
        assert response.status_code == 200

        languages = response.json()
        assert "languages" in languages
        assert "python" in languages["languages"]

        # Test getting specific configuration
        response = client.get("/api/v1/quality/config/python/STANDARD")
        assert response.status_code == 200

        config = response.json()
        assert "config" in config
        assert config["config"]["language"] == "python"

    def test_health_monitoring_endpoint(self, client):
        """Test health monitoring endpoint"""
        response = client.get("/api/v1/quality/health")
        assert response.status_code == 200

        health = response.json()
        assert "status" in health
        assert "pipeline_status" in health
        assert "dependencies" in health

    @pytest.mark.asyncio
    async def test_end_to_end_code_generation_integration(self, client):
        """Test that quality pipeline integrates with code generation"""
        # This test would require setting up a mock code generation request
        # but verifies that the integration points exist

        # Test that CodeGenerationService can import quality pipeline
        try:
            from app.api.v1.services.code_generation import CodeGenerationService

            service = CodeGenerationService()

            # Check that quality pipeline is initialized
            assert hasattr(service, "quality_pipeline")
            assert service.quality_pipeline is not None

        except ImportError as e:
            pytest.skip(f"Code generation service not available: {e}")

    def test_quality_middleware_fallback(self):
        """Test that enhanced quality middleware has proper fallback"""
        try:
            from app.api.v1.services.enhanced_quality_middleware import (
                EnhancedCodeGenerationQualityMiddleware,
            )

            middleware = EnhancedCodeGenerationQualityMiddleware()
            assert middleware is not None

            # Test that it has fallback to original middleware
            assert hasattr(middleware, "_original_middleware")

        except ImportError as e:
            pytest.skip(f"Enhanced quality middleware not available: {e}")

    def test_dependency_availability(self):
        """Test that all required dependencies are available"""
        dependencies = [
            "esprima",
            "vulture",
            "bandit",
            "safety",
            "pylint",
            "radon",
            "mccabe",
        ]

        for dep in dependencies:
            try:
                __import__(dep)
            except ImportError:
                pytest.fail(f"Required dependency {dep} is not available")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
