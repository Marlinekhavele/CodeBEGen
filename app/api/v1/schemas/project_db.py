from typing import List, Dict, Any
from pydantic import BaseModel


class DBFileResponse(BaseModel):
    name: str
    path: str


class DBFileListSuccessResponse(BaseModel):
    status_code: int
    success: bool
    message: str
    data: List[DBFileResponse]


class DBTableResponse(BaseModel):
    name: str


class DBTableListSuccessResponse(BaseModel):
    status_code: int
    success: bool
    message: str
    data: List[DBTableResponse]

class TableRowsSuccessResponse(BaseModel):
    status_code: int
    success: bool
    message: str
    data: List[Dict[str, Any]]

class TableData(BaseModel):
    name: str
    rows: List[Dict[str, Any]]


class FullDBViewItem(BaseModel):
    db_file: str
    path: str
    tables: List[TableData]


class FullDBViewResponse(BaseModel):
    status_code: int
    success: bool
    message: str
    data: List[FullDBViewItem]
