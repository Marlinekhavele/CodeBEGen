import base64
from typing import Optional

from pydantic import BaseModel, Field, validator

from app.api.v1.schemas.response import SuccessResponse


class EndpointFileRequest(BaseModel):
    """
    Request schema for editor file operations
    """

    project_id: str = Field(
        ..., description="Project_ID returned from project initialization"
    )
    endpoint_path: str = Field(
        ..., description="Path of the endpoint (e.g., 'api/v1/editor')"
    )
    content_base64: Optional[str] = Field(
        None, description="Base64-encoded file content"
    )
    method: str = Field(
        ...,
        description="HTTP method for the endpoint (GET|POST|PUT|DELETE)",
    )
    description: Optional[str] = Field(None, description="Description of the endpoint")

    @validator("method")
    def validate_method(cls, v):
        if v.upper() not in ["GET", "POST", "PUT", "DELETE"]:
            raise ValueError("Method must be one of: GET, POST, PUT, DELETE")
        return v.upper()  # Convert to uppercase

    @property
    def content(self) -> Optional[str]:
        """Decode base64 content to plain text when needed"""
        if self.content_base64:
            try:
                return base64.b64decode(self.content_base64).decode("utf-8")
            except Exception as e:
                raise ValueError(f"Invalid base64 content: {str(e)}")
        return None


class EndpointFileResponse(BaseModel):
    """
    Response schema for editor file operations
    """

    project_id: str
    endpoint_path: str
    file_path: str
    content_base64: Optional[str] = None
    commit_hash: Optional[str] = None
    file_hash: Optional[str] = None
    message: str
    method: str
    endpoint_id: Optional[str] = None
    description: Optional[str] = None


class EndpointSuccessResponse(SuccessResponse):
    data: EndpointFileResponse
