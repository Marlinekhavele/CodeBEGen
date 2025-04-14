import json
import pytest
from fastapi import status
from fastapi.testclient import TestClient

# Mock classes and responses for testing
class MockCodeGenerationService:
    async def generate_code(self, request):
        return {
            "success": True,
            "message": "Code generation successful",
            "result": {
                "endpoint": {
                    "file_path": "routes/test.py",
                    "generated_code": "def test_endpoint(): pass",
                    "content_base64": "ZGVmIHRlc3RfZW5kcG9pbnQoKTogcGFzcw==",
                    "file_hash": "abc123"
                },
                "language": "python",
                "file_extension": ".py"
            }
        }

@pytest.fixture
def client():
    from main import app
    from app.api.v1.routes.code_generation import CodeGenerationService
    
    # Replace the actual service with our mock
    app.dependency_overrides[CodeGenerationService] = MockCodeGenerationService
    return TestClient(app)

@pytest.fixture
def valid_request():
    return {
        "project_id": "test-project",
        "prompt": "Create a test endpoint",
        "language": "python",
        "method": "GET",
        "endpoint_path": "/api/v1/test"
    }

class TestCodeGeneration:
    def test_generate_code_success(self, client, valid_request):
        """Test successful code generation via HTTP endpoint"""
        response = client.post("/api/v1/generate", json=valid_request)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "result" in data
        assert data["result"]["language"] == "python"

    def test_generate_code_invalid_request(self, client):
        """Test code generation with invalid request data"""
        invalid_request = {
            "project_id": "test-project",
            # Missing required 'prompt' field
            "language": "python"
        }
        
        response = client.post("/api/v1/generate", json=invalid_request)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_websocket_code_generation(self, client, valid_request):
        """Test WebSocket code generation streaming"""
        with client.websocket_connect("/api/v1/generate/stream") as websocket:
            # Should receive connection confirmation
            data = websocket.receive_json()
            assert data["status"] == "connected"
            
            # Send generation request
            websocket.send_text(json.dumps(valid_request))
            
            # Collect all messages until we receive the final 'complete' status
            received_progress = False
            while True:
                data = websocket.receive_json()
                
                if data["status"] == "progress":
                    received_progress = True
                    assert "stage" in data
                    assert "message" in data
                elif data["status"] == "completed":
                    assert "stage" in data
                    assert "result" in data
                elif data["status"] == "info":
                    assert "message" in data
                elif data["status"] == "complete":
                    assert "result" in data
                    break
                elif data["status"] == "error":
                    pytest.fail(f"Received error: {data['message']}")
                
            # Verify we received at least one progress message
            assert received_progress, "No progress messages were received"

    @pytest.mark.asyncio
    async def test_websocket_invalid_request(self, client):
        """Test WebSocket with invalid request data"""
        invalid_request = {
            "project_id": "test-project",
            # Missing required 'prompt' field
            "language": "python"
        }
        
        with client.websocket_connect("/api/v1/generate/stream") as websocket:
            # Should receive connection confirmation
            data = websocket.receive_json()
            assert data["status"] == "connected"
            
            # Send invalid request
            websocket.send_text(json.dumps(invalid_request))
            
            # Should receive error message
            data = websocket.receive_json()
            assert data["status"] == "error"
            assert "Invalid request parameters" in data["message"]

# Additional test class for component generation
class TestComponentGeneration:
    def test_endpoint_generation(self, client, valid_request):
        """Test generation of endpoint component"""
        response = client.post("/api/v1/generate", json=valid_request)
        data = response.json()
        
        assert "endpoint" in data["result"]
        endpoint = data["result"]["endpoint"]
        assert "file_path" in endpoint
        assert "generated_code" in endpoint
        assert "content_base64" in endpoint
        assert "file_hash" in endpoint

    @pytest.mark.parametrize("language", ["python", "javascript"])
    def test_language_support(self, client, valid_request, language):
        """Test code generation for different languages"""
        valid_request["language"] = language
        response = client.post("/api/v1/generate", json=valid_request)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["result"]["language"] == language