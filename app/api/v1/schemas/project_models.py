from typing import List

from pydantic import BaseModel


class ModelResponse(BaseModel):
    """Schema for a single model response"""

    name: str


class ModelListResponse(BaseModel):
    """Schema for a list of models"""

    models: List[ModelResponse]


class ModelListSuccessResponse(BaseModel):
    """Success response schema for the model list endpoint"""

    status_code: int
    message: str
    data: List[ModelResponse]


class ModelContentResponse(BaseModel):
    """Schema for a model content response"""

    name: str
    format: str
    content: str
    content_base64: str


class ModelContentSuccessResponse(BaseModel):
    """Success response schema for the model content endpoint"""

    status_code: int
    success: bool
    message: str
    data: ModelContentResponse
