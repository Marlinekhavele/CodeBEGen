from typing import List
from pydantic import BaseModel

class SchemaResponse(BaseModel):
    """
    Schema for a single schema response
    """
    name: str

class SchemaListResponse(BaseModel):
    """
    Schema for a list of schemas
    """
    schemas: List[SchemaResponse]

class SchemaListSuccessResponse(BaseModel):
    """
    Success response schema for the schema list endpoint
    """
    status_code: int
    message: str
    data: List[SchemaResponse]
    
class SchemaContentResponse(BaseModel):
    """
    Schema for a schema content response
    """
    name: str
    format: str
    content: str
    content_base64: str


class SchemaContentSuccessResponse(BaseModel):
    """
    Success response schema for the schema content endpoint
    """
    status_code: int
    success: bool
    message: str
    data: SchemaContentResponse
