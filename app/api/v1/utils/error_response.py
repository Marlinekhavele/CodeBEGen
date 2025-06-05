from typing import Any, Dict, Optional

from fastapi.responses import JSONResponse


def error_response(
    status_code: int,
    message: str = "Error",
    detail: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
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
    if context is not None:
        content["context"] = context

    return JSONResponse(status_code=status_code, content=content)
