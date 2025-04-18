from typing import List

from pydantic import BaseModel

from app.api.v1.schemas.response import SuccessResponse


class EndpointResponse(BaseModel):
    path: str
    method: str

    class Config:
        from_attributes = True


class EndpointListResponse(BaseModel):
    endpoints: List[EndpointResponse]


class EndpointListSuccessResponse(SuccessResponse):
    data: List[EndpointResponse]
