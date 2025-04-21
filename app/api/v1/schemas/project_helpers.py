from typing import List
from pydantic import BaseModel

class HelperResponse(BaseModel):
    """
    Model for a single helper response
    """
    name: str
    type: str = "" # This specify helper type

class HelperListResponse(BaseModel):
    """
    Model for a list of helpers
    """
    helpers: List[HelperResponse]

class HelperListSuccessResponse(BaseModel):
    """
    Success response model for the helper list endpoint
    """
    status_code: int
    message: str
    data: List[HelperResponse]
    
class HelperContentResponse(BaseModel):
    """
    Model for a helper content response
    """
    name: str
    type: str  # This specify helper type
    format: str
    content: str
    content_base64: str


class HelperContentSuccessResponse(BaseModel):
    """
    Success response model for the helper content endpoint
    """
    status_code: int
    success: bool
    message: str
    data: HelperContentResponse