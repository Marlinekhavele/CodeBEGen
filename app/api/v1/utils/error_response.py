from fastapi.responses import JSONResponse
from typing import Optional

def error_response(
    status_code: int,
    message: str = "Error",
    detail: Optional[str] = None
) -> JSONResponse:
    """
    Generate a standardized error response.
    """
    content = {
        "status_code": status_code,
        "status": False,
        "message": message,
    }
    if detail is not None:
        content["detail"] = detail
    
    return JSONResponse(
        status_code=status_code,
        content=content
    )