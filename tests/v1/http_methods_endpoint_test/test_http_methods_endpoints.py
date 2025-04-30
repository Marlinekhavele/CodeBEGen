import json
import unittest
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from app.api.v1.models.http_methods_test_endpoint import TestRequestPayload
from app.api.v1.routes.http_methods_test_endpoint import (
    test_project_endpoint as endpoint_function,
)


class TestHttpEndpoints(unittest.IsolatedAsyncioTestCase):
    """Tests for the HTTP methods endpoint handler"""

    @patch("app.api.v1.routes.http_methods_test_endpoint.TestEndpointService")
    @patch("uuid.uuid4")
    async def test_success_response(self, mock_uuid4, MockServiceClass):
        """Test the success path of the endpoint handler"""
        # Setup mocks
        request_id = "00000000-0000-0000-0000-000000000000"
        mock_uuid4.return_value = uuid.UUID(request_id)

        # Mock service
        mock_service_instance = MockServiceClass.return_value
        # Define mock response that matches what your service returns
        mock_response = MagicMock()
        mock_response.statusCode = 200
        mock_response.success = True
        mock_response.request_id = request_id
        mock_response.responseBody = {"message": "success"}
        mock_response.responseHeaders = {"content-type": "application/json"}
        mock_response.timeTaken = 0.1
        mock_response.size = 100
        mock_response.contentType = "application/json"
        mock_response.cookies = {}
        mock_response.redirects = None
        mock_response.timestamp = datetime.utcnow()

        # Setup service execute_test to return our mock
        mock_service_instance.execute_test = AsyncMock(return_value=mock_response)

        # Create test payload
        project_id = "test-project"
        payload = TestRequestPayload(
            httpMethod="GET",
            endpointUrl="http://test-project/api/test",
            headers={"Authorization": "Bearer token"},
            queryParams={"key": "value"},
            timeout=10,
            follow_redirects=True,
            requestBody=None,
            formData=None,
            multipartData=None,
            contentType="application/json",
            auth=None,
        )

        # Call function under test
        response = await endpoint_function(project_id, payload)

        # Verify service was called with correct arguments
        mock_service_instance.execute_test.assert_called_once()

        # Verify response is as expected
        self.assertIsInstance(response, JSONResponse)
        self.assertEqual(response.status_code, 200)

        # Parse response content
        response_content = json.loads(response.body)
        self.assertTrue(response_content["success"])
        self.assertEqual(response_content["status_code"], 200)
        self.assertEqual(response_content["message"], "Request completed successfully")
        self.assertIn("data", response_content)

    @patch("app.api.v1.routes.http_methods_test_endpoint.TestEndpointService")
    async def test_http_exception_handling(self, MockServiceClass):
        """Test endpoint handler propagates HTTP exceptions"""
        # Mock service
        mock_service_instance = MockServiceClass.return_value

        # Make execute_test raise HTTPException
        exception = HTTPException(status_code=404, detail="Not found")
        mock_service_instance.execute_test = AsyncMock(side_effect=exception)

        # Create test payload
        project_id = "test-project"
        payload = TestRequestPayload(
            httpMethod="GET",
            endpointUrl="http://test-project/api/not-found",
            headers={},
            queryParams={},
            timeout=10,
            follow_redirects=True,
            requestBody=None,
            formData=None,
            multipartData=None,
            contentType="application/json",
            auth=None,
        )

        # Call function and expect exception
        with self.assertRaises(HTTPException) as context:
            await endpoint_function(project_id, payload)

        # Verify exception details
        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.detail, "Not found")

    @patch("app.api.v1.routes.http_methods_test_endpoint.TestEndpointService")
    async def test_general_exception_handling(self, MockServiceClass):
        """Test endpoint handler handles general exceptions"""
        # Mock service
        mock_service_instance = MockServiceClass.return_value

        # Make execute_test raise a general exception
        exception = Exception("Something went wrong")
        mock_service_instance.execute_test = AsyncMock(side_effect=exception)

        # Create test payload
        project_id = "test-project"
        payload = TestRequestPayload(
            httpMethod="GET",
            endpointUrl="http://test-project/api/test",
            headers={},
            queryParams={},
            timeout=10,
            follow_redirects=True,
            requestBody=None,
            formData=None,
            multipartData=None,
            contentType="application/json",
            auth=None,
        )

        # Call function
        response = await endpoint_function(project_id, payload)

        # Verify error response
        self.assertIsInstance(response, JSONResponse)
        self.assertEqual(response.status_code, 500)

        # Parse response content
        response_content = json.loads(response.body)
        self.assertFalse(response_content["status"])
        self.assertEqual(response_content["status_code"], 500)
        self.assertEqual(response_content["message"], "Error while testing project")
        self.assertEqual(response_content["detail"], "Something went wrong")


if __name__ == "__main__":
    unittest.main()
