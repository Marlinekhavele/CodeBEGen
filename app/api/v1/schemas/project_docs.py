from typing import List

from pydantic import BaseModel


class DocsResponse(BaseModel):
    """
    Model for a single docs response
    """

    name: str
    type: str = ""  # This specify doc type


class DocsListResponse(BaseModel):
    """
    Model for a list of docs
    """

    docs: List[DocsResponse]


class DocsListSuccessResponse(BaseModel):
    """
    Success response model for the docs list endpoint
    """

    status_code: int
    message: str
    data: List[DocsResponse]


class DocsContentResponse(BaseModel):
    """
    Model for a docs content response
    """

    name: str
    type: str  # This specify doc type
    format: str
    content: str
    content_base64: str


class DocsContentSuccessResponse(BaseModel):
    """
    Success response model for the docs content endpoint
    """

    status_code: int
    success: bool
    message: str
    data: DocsContentResponse
