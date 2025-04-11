from pydantic import BaseModel
from typing import Optional



class SuccessResponse(BaseModel):
    status_code: Optional[int] = None
    success: bool
    message: str
    data: Optional[dict] = None    

class ErrorResponse(BaseModel):
    status_code: int
    message: str
    detail: Optional[str] = None

