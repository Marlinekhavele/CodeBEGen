from typing import Any, List, Optional

from pydantic import BaseModel

from app.api.v1.schemas.response import SuccessResponse


# Project structure response schemas
class FileNode(BaseModel):
    type: str  # "file" or "directory"
    name: str
    path: str
    extension: Optional[str] = None
    size: Optional[int] = None


class DirectoryNode(BaseModel):
    type: str  # always "directory"
    name: str
    path: str
    children: List[
        Any
    ]  # List[Union[FileNode, DirectoryNode]] - using Any for recursive structure


class ProjectStructureData(BaseModel):
    project_id: str
    structure: DirectoryNode


class ProjectStructureSuccessResponse(SuccessResponse):
    data: ProjectStructureData


# Project modules response schemas
class ModuleInfo(BaseModel):
    name: str
    path: str
    full_path: str
    extension: str


class ProjectModules(BaseModel):
    models: List[ModuleInfo]
    endpoints: List[ModuleInfo]
    schemas: List[ModuleInfo]
    utils: List[ModuleInfo]
    controllers: List[ModuleInfo]
    routes: List[ModuleInfo]
    helpers: List[ModuleInfo]
    others: List[ModuleInfo]


class ProjectModulesData(BaseModel):
    project_id: str
    modules: ProjectModules


class ProjectModulesSuccessResponse(SuccessResponse):
    data: ProjectModulesData


# File content response schemas
class FileContentData(BaseModel):
    project_id: str
    file_path: str
    name: str
    format: str
    content: str
    content_base64: str
    extension: str


class FileContentSuccessResponse(SuccessResponse):
    data: FileContentData


# Search results response schemas
class SearchMatch(BaseModel):
    line_number: int
    line: str
    context: str


class SearchResult(BaseModel):
    name: str
    path: str
    full_path: str
    matches: List[SearchMatch]
    match_count: int


class SearchResultsData(BaseModel):
    project_id: str
    query: str
    results: List[SearchResult]


class SearchResultsSuccessResponse(SuccessResponse):
    data: SearchResultsData
