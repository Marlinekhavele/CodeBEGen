"""
Test script to verify the auto-fix integration with the test endpoint service.
This will test the complete workflow of detecting and fixing Pydantic configuration errors.
"""

import asyncio
import logging
from uuid import uuid4

from app.api.v1.models.http_methods_test_endpoint import TestRequestPayload
from app.api.v1.services.http_methods_test_endpoint_service import TestEndpointService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_pydantic_error_auto_fix():
    """
    Test the auto-fix functionality with a real Pydantic configuration error.
    """  # Create a test payload that should trigger the Pydantic error
    payload = TestRequestPayload(
        httpMethod="POST",
        endpointUrl="http://book-store-g2gl46/book",  # Fixed: use /book instead of /books
        headers={"Content-Type": "application/json"},
        queryParams={},
        timeout=30,
        follow_redirects=True,
        requestBody={
            "title": "Test Book",
            "author": "Test Author",
            "description": "A test book",
        },
        formData=None,
        multipartData=None,
        contentType="application/json",
        auth=None,
    )

    # Test with the book-store project that has the Pydantic error
    project_id = "book-store-g2gl46"
    request_id = str(uuid4())

    # Initialize the test service
    test_service = TestEndpointService()

    logger.info("Testing without auto-fix first...")

    try:  # First test without auto-fix to confirm the error exists
        response = await test_service.execute_test(
            project_id=project_id, path="book", payload=payload, request_id=request_id
        )

        logger.info(
            f"Test without auto-fix result: Success={response.success}, Status={response.statusCode}"
        )
        if not response.success:
            logger.info(f"Error details: {response.responseBody}")

    except Exception as e:
        logger.info(f"Expected error without auto-fix: {str(e)}")

        # Check if it's the Pydantic configuration error we're looking for
        if "from_attributes" in str(e) and "use from_orm" in str(e):
            logger.info("✓ Confirmed Pydantic configuration error exists")
            # Now test with auto-fix enabled
            logger.info("Testing WITH auto-fix enabled...")

            try:
                response_with_fix = await test_service.execute_test_with_auto_fix(
                    project_id=project_id,
                    path="book",
                    payload=payload,
                    request_id=str(uuid4()),
                    auto_fix=True,
                    max_retries=2,
                )

                logger.info(
                    f"Test WITH auto-fix result: Success={response_with_fix.success}, Status={response_with_fix.statusCode}"
                )

                if response_with_fix.success:
                    logger.info("✓ Auto-fix successfully resolved the error!")
                    logger.info(f"Response: {response_with_fix.responseBody}")
                else:
                    logger.warning(
                        f"✗ Auto-fix was unable to resolve the error: {response_with_fix.responseBody}"
                    )

            except Exception as auto_fix_error:
                logger.error(f"✗ Auto-fix failed with exception: {str(auto_fix_error)}")
        else:
            logger.warning(f"Unexpected error type: {str(e)}")


if __name__ == "__main__":
    asyncio.run(test_pydantic_error_auto_fix())
