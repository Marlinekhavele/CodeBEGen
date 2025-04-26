import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.api.v1.schemas.project_db import (
    DBFileListSuccessResponse,
    DBFileResponse,
    DBTableListSuccessResponse,
    DBTableResponse,
    FullDBViewResponse,
    TableRowsSuccessResponse,
)
from app.api.v1.services.project_db import GetProjectDatabases
from app.api.v1.utils.error_response import error_response
from app.api.v1.utils.success_response import success_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["database"])


@router.get("/projects/{project_id}/db/files", response_model=DBFileListSuccessResponse)
async def list_database_files(project_id: str):
    """
    List all SQLite DB files in the storage/db directory.
    """
    try:
        dbs = await GetProjectDatabases.list_db_files(project_id)

        if isinstance(dbs, JSONResponse):
            return dbs

        result = [DBFileResponse(**item) for item in dbs]

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Database files listed successfully",
            data=result,
        )
    except Exception as e:
        logger.error(f"Error listing DB files: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to list DB files",
            detail=str(e),
        )


@router.get(
    "/projects/{project_id}/db/{db_filename}/tables",
    response_model=DBTableListSuccessResponse,
)
async def list_tables_in_db(project_id: str, db_filename: str):
    """
    Get all table names from a specific .sqlite3 file.
    """
    try:
        tables = await GetProjectDatabases.get_tables_in_db(project_id, db_filename)

        if isinstance(tables, JSONResponse):
            return tables

        result = [DBTableResponse(name=tbl) for tbl in tables]

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Tables retrieved successfully",
            data=result,
        )
    except Exception as e:
        logger.error(f"Error fetching tables: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to fetch tables",
            detail=str(e),
        )


@router.get(
    "/projects/{project_id}/db/{db_filename}/tables/{table_name}/rows",
    response_model=TableRowsSuccessResponse,
)
async def get_table_rows(
    project_id: str, db_filename: str, table_name: str, limit: int = 50
):
    """
    Get row contents of a table in a .sqlite3 DB.
    """
    try:
        rows = await GetProjectDatabases.get_table_rows(
            project_id, db_filename, table_name, limit
        )

        if isinstance(rows, JSONResponse):
            return rows

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Table rows retrieved successfully",
            data=rows,
        )
    except Exception as e:
        logger.error(f"Error fetching rows: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to fetch table rows",
            detail=str(e),
        )


@router.get("/projects/{project_id}/db/full-view", response_model=FullDBViewResponse)
async def get_full_db_view(project_id: str, row_limit: int = 10):
    """
    Get all DB files, tables in each DB, and sample rows from each table.
    """
    try:
        view = await GetProjectDatabases.get_full_db_view(project_id, row_limit)

        if isinstance(view, JSONResponse):
            return view

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Full DB view retrieved successfully",
            data=view,
        )
    except Exception as e:
        logger.error(f"Error retrieving full DB view: {str(e)}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Internal Server Error",
            detail=str(e),
        )
