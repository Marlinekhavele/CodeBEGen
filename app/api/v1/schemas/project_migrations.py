from typing import List, Optional

from pydantic import BaseModel


class VersionResponse(BaseModel):
    """
    Model for a single alembic version response
    """

    id: str
    name: str
    revision: Optional[str] = None
    filename: str
    timestamp: Optional[str] = None


class VersionListResponse(BaseModel):
    """
    Model for a list of versions
    """

    versions: List[VersionResponse]


class VersionListSuccessResponse(BaseModel):
    """
    Success response model for the version list endpoint
    """

    status_code: int
    message: str
    data: List[VersionResponse]


class VersionContentResponse(BaseModel):
    """
    Model for a version content response
    """

    id: str
    name: str
    revision: Optional[str] = None
    filename: str
    format: str
    content: str
    content_base64: str
    timestamp: Optional[str] = None


class VersionContentSuccessResponse(BaseModel):
    """
    Success response model for the version content endpoint
    """

    status_code: int
    success: bool
    message: str
    data: VersionContentResponse
