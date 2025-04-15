from uuid import UUID

from pydantic import BaseModel

from app.api.v1.schemas.response import SuccessResponse


class ProjectInitRequest(BaseModel):
    project_name: str
    language: str
    framework: str


class ProjectInitResponse(BaseModel):
    project_id: str
    project_url: str
    language: str
    framework: str


class ProjectInitSuccessResponse(SuccessResponse):
    data: ProjectInitResponse


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: str
    slug: str
    language: str
    framework: str

    class Config:
        from_attributes = True
