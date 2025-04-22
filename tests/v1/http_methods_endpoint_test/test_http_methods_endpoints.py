import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.api.v1.models.http_methods_test_endpoint import TestRequestPayload
from app.api.v1.routes.http_methods_test_endpoint import run_test_endpoint


class TestRunTestEndpoint(unittest.IsolatedAsyncioTestCase):
    @patch("httpx.AsyncClient")
    async def test_run_test_endpoint_success(self, mock_async_client):
        payload = TestRequestPayload(
            httpMethod="GET",
            endpointUrl="https://example.com",
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

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": "success"}
        mock_response.content = b'{"message": "success"}'
        mock_response.headers = {"content-type": "application/json"}
        mock_response.cookies = {}
        mock_response.history = []

        mock_async_client.return_value.__aenter__.return_value.request = AsyncMock(
            return_value=mock_response
        )

        response = await run_test_endpoint(payload)

        self.assertEqual(response.success, True)
        self.assertEqual(response.statusCode, 200)
        self.assertEqual(response.responseBody, {"message": "success"})
        self.assertEqual(response.contentType, "application/json")

    @patch("httpx.AsyncClient")
    async def test_run_test_endpoint_put_success(self, mock_async_client):
        payload = TestRequestPayload(
            httpMethod="PUT",
            endpointUrl="https://example.com/resource/1",
            headers={"Content-Type": "application/json"},
            requestBody={"key": "value"},
            queryParams=None,
            timeout=10,
            follow_redirects=True,
            formData=None,
            multipartData=None,
            contentType="application/json",
            auth=None,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": "PUT request processed successfully."
        }
        mock_response.content = b'{"message": "PUT request processed successfully."}'
        mock_response.headers = {"content-type": "application/json"}
        mock_response.cookies = {}
        mock_response.history = []

        mock_async_client.return_value.__aenter__.return_value.request = AsyncMock(
            return_value=mock_response
        )

        response = await run_test_endpoint(payload)

        self.assertEqual(response.success, True)
        self.assertEqual(response.statusCode, 200)
        responseBody = {"message": "PUT request processed successfully."}
        self.assertEqual(
            response.responseBody,
            {"message": "PUT request processed successfully.", "data": responseBody},
        )
        self.assertEqual(response.contentType, "application/json")

    @patch("httpx.AsyncClient")
    async def test_run_test_endpoint_delete_success(self, mock_async_client):
        payload = TestRequestPayload(
            httpMethod="DELETE",
            endpointUrl="https://example.com/resource/1",
            headers={"Authorization": "Bearer token"},
            requestBody=None,
            queryParams=None,
            timeout=10,
            follow_redirects=True,
            formData=None,
            multipartData=None,
            contentType="application/json",
            auth=None,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": "DELETE request processed successfully."
        }
        mock_response.content = b'{"message": "DELETE request processed successfully."}'
        mock_response.headers = {"content-type": "application/json"}
        mock_response.cookies = {}
        mock_response.history = []

        mock_async_client.return_value.__aenter__.return_value.request = AsyncMock(
            return_value=mock_response
        )

        response = await run_test_endpoint(payload)

        self.assertEqual(response.success, True)
        self.assertEqual(response.statusCode, 200)
        responseBody = {"message": "DELETE request processed successfully."}
        self.assertEqual(
            response.responseBody,
            {
                "message": "DELETE request processed successfully.",
                "data": responseBody,
            },
        )
        self.assertEqual(response.contentType, "application/json")

    @patch("httpx.AsyncClient")
    async def test_run_test_endpoint_http_exception(self, mock_async_client):
        payload = TestRequestPayload(
            httpMethod="GET",
            endpointUrl="https://example.com",
            headers=None,
            queryParams=None,
            timeout=10,
            follow_redirects=True,
            requestBody=None,
            formData=None,
            multipartData=None,
            contentType="application/json",
            auth=None,
        )

        mock_async_client.return_value.__aenter__.return_value.request = AsyncMock(
            side_effect=Exception("Request failed")
        )

        with self.assertRaises(HTTPException) as context:
            await run_test_endpoint(payload)

        self.assertEqual(context.exception.status_code, 500)
        self.assertIn("An error occurred", context.exception.detail)


if __name__ == "__main__":
    unittest.main()
