import json
import time
import uuid
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, status

from app.api.v1.models.http_methods_test_endpoint import (
    AuthType,
    TestRequestPayload,
    TestResponsePayload,
)
from app.api.v1.utils.http_methods_test_endpoint_helpers import add_auth_to_request

router = APIRouter(tags=["test-endpoint"])


@router.post("/test-endpoint", response_model=TestResponsePayload)
async def run_test_endpoint(payload: TestRequestPayload):
    """
    Test an API endpoint by sending an HTTP request to the specified URL.

    This function builds an HTTP request based on the provided payload, executes the request,
    and returns the response in a structured format.

    Args:
        \n
        payload (TestRequestPayload): The payload containing details of the request to be sent.
            - endpointUrl (HttpUrl): The URL of the API endpoint.
            - httpMethod (str): The HTTP method (e.g., GET, POST, PUT, DELETE).
            - headers (Optional[Dict[str, str]]): HTTP headers to include in the request.
            - queryParams (Optional[Dict[str, str]]): Query parameters to include in the request.
            - requestBody (Optional[Any]): The body of the request (e.g., JSON or form data).
            - formData (Optional[List[FormDataItem]]): Form data for `application/x-www-form-urlencoded` requests.
            - multipartData (Optional[List[Union[FormDataItem, FileUpload]]]): Multipart data for file uploads.
            - auth (Optional[Auth]): Authentication details (e.g., Basic, Bearer, API Key).
            - timeout (Optional[int]): Timeout for the request in seconds (default: 30).
            - follow_redirects (Optional[bool]): Whether to follow redirects (default: True).
            - contentType (Optional[str]): Content-Type of the request (default: application/json).

    Returns:
    \n
        TestResponsePayload: A structured response containing:
            - request_id (str): A unique ID for the request.
            - success (bool): Whether the request was successful (status code < 400).
            - statusCode (int): The HTTP status code of the response.
            - responseBody (Any): The body of the response.
            - responseHeaders (Dict[str, str]): The headers of the response.
            - timeTaken (float): The time taken to execute the request (in seconds).
            - size (int): The size of the response (in bytes).
            - contentType (Optional[str]): The Content-Type of the response.
            - cookies (Optional[Dict[str, str]]): Cookies returned in the response.
            - redirects (Optional[List[str]]): List of redirect URLs (if any).
            - timestamp (datetime): The timestamp when the response was received.

    Raises:
    \n
        HTTPException: If the request fails or an error occurs during processing.
            - 400: If the request payload is invalid (e.g., invalid JSON in requestBody).
            - 500: If the request fails due to a server or network error.

    **Examples:**

    GET Request:
    \n
        payload = {
           "endpointUrl": "https://example.com/resource",
           "httpMethod": "GET",
           "headers": {"Authorization": "Bearer token"},
           "queryParams": {"key": "value"},
           "timeout": 10,
           "follow_redirects": True
        }


    POST Request:
    \n
        payload = {
            "endpointUrl": "https://example.com/resource",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "requestBody": {"key": "value"},
            "timeout": 10
        }

    PUT Request:
    \n
        payload = {
            "endpointUrl": "https://example.com/resource/1",
            "httpMethod": "PUT",
            "headers": {"Content-Type": "application/json"},
            "requestBody": {"key": "value"},
            "timeout": 10
        }

    PATCH Request:
    \n
        payload = {
            "endpointUrl": "https://example.com/resource/1",
            "httpMethod": "PATCH",
            "headers": {"Content-Type": "application/json"},
            "requestBody": {"key": "updated_value"},
            "timeout": 10
        }

    DELETE Request:
    \n
        payload = {
            "endpointUrl": "https://example.com/resource/1",
            "httpMethod": "DELETE",
            "headers": {"Authorization": "Bearer token"},
            "timeout": 10
        }
    """
    if payload.httpMethod in ["POST", "PUT", "PATCH"] and not any(
        [payload.requestBody, payload.formData, payload.multipartData]
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body, form data, or multipart data is required for POST, PUT, and PATCH requests.",
        )

    if payload.httpMethod == "DELETE" and any(
        [payload.requestBody, payload.formData, payload.multipartData]
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DELETE requests should not include a body.",
        )

    request_id = str(uuid.uuid4())

    try:
        request_kwargs = {
            "method": payload.httpMethod,
            "url": str(payload.endpointUrl),
            "timeout": payload.timeout,
            "follow_redirects": payload.follow_redirects,
        }

        if payload.headers:
            request_kwargs["headers"] = payload.headers

        if payload.contentType and not (
            payload.headers
            and "content-type" in [h.lower() for h in payload.headers.keys()]
        ):
            if "headers" not in request_kwargs:
                request_kwargs["headers"] = {}
            request_kwargs["headers"]["Content-Type"] = payload.contentType

        if payload.queryParams:
            request_kwargs["params"] = payload.queryParams

        if payload.auth and payload.auth.type != AuthType.NONE:
            request_kwargs = add_auth_to_request(request_kwargs, payload.auth)

        if payload.requestBody and payload.contentType == "application/json":
            if isinstance(payload.requestBody, str):
                try:
                    payload.requestBody = json.loads(payload.requestBody)
                except json.JSONDecodeError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid JSON string in requestBody",
                    )
            request_kwargs["json"] = payload.requestBody
        elif payload.requestBody:
            request_kwargs["data"] = json.dumps(payload.requestBody)
        elif payload.formData:
            form_data = {
                item.key: item.value for item in payload.formData if not item.disabled
            }
            request_kwargs["data"] = form_data
        elif payload.multipartData:
            pass

        start_time = time.time()
        async with httpx.AsyncClient() as client:
            response = await client.request(**request_kwargs)
        end_time = time.time()

        try:
            response_body = response.json()
        except json.JSONDecodeError:
            response_body = response.text

        if payload.httpMethod in ["PUT", "DELETE"]:
            response_body = {
                "message": f"{payload.httpMethod} request processed successfully.",
                "data": response_body,
            }

        response_size = len(response.content)

        response_data = TestResponsePayload(
            request_id=request_id,
            success=response.status_code < 400,
            statusCode=response.status_code,
            responseBody=response_body,
            responseHeaders=dict(response.headers),
            timeTaken=end_time - start_time,
            size=response_size,
            contentType=response.headers.get("content-type"),
            cookies=dict(response.cookies),
            redirects=(
                [str(r.url) for r in response.history] if response.history else None
            ),
            timestamp=datetime.utcnow(),
        )

        return response_data

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Request failed: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}",
        )
