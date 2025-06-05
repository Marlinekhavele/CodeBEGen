import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, HttpUrl, validator


class AuthType(str, Enum):
    NONE = "none"
    BASIC = "basic"
    BEARER = "bearer"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"


class FormDataItem(BaseModel):
    key: str
    value: str
    disabled: bool = False


class FileUpload(BaseModel):
    key: str
    filename: str
    content_type: str
    disabled: bool = False


class Auth(BaseModel):
    type: AuthType
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    key_name: Optional[str] = None
    key_value: Optional[str] = None
    add_to: Optional[str] = "header"  # header or query


class TestRequestPayload(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    endpointUrl: HttpUrl
    httpMethod: str
    headers: Optional[Dict[str, str]] = None
    queryParams: Optional[Dict[str, str]] = None
    requestBody: Optional[Any] = None
    formData: Optional[List[FormDataItem]] = None
    multipartData: Optional[List[Union[FormDataItem, FileUpload]]] = None
    auth: Optional[Auth] = None
    timeout: Optional[int] = 30
    follow_redirects: Optional[bool] = True
    contentType: Optional[str] = "application/json"
    save_request: Optional[bool] = False
    environment_id: Optional[str] = None

    @validator("httpMethod")
    def validate_http_method(cls, v):
        allowed_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
        if v.upper() not in allowed_methods:
            raise ValueError(f"HTTP method must be one of {allowed_methods}")
        return v.upper()


class TestResponsePayload(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    success: bool
    statusCode: int
    responseBody: Any
    responseHeaders: Dict[str, str] = {}
    timeTaken: float = 0.0
    size: int = 0
    contentType: Optional[str] = None
    cookies: Optional[Dict[str, str]] = None
    redirects: Optional[List[str]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CodeFixPayload(BaseModel):
    """Payload model for code fixing requests"""

    context: Optional[str] = Field(
        None, description="Additional context about the error"
    )
    error_message: str = Field(..., description="The error message to fix")
    file_path: str = Field(..., description="Path to the file that needs fixing")
    language: str = Field(
        default="python", description="Programming language of the file"
    )
    project_id: str = Field(..., description="ID of the project containing the file")


class CodeFixResponse(BaseModel):
    """Response model for code fixing requests"""

    success: bool
    message: str
    fixed_code: Optional[str] = None
    file_path: Optional[str] = None
    changes_applied: bool = False
    error_details: Optional[str] = None
