import base64
import sqlite3
import tempfile
import requests
import logging

from fastapi import status
from fastapi.responses import JSONResponse
from app.api.v1.utils.error_response import error_response
from config import settings

logger = logging.getLogger(__name__)


class GetProjectDatabases:
    @staticmethod
    async def list_db_files(project_id: str):
        """
        Asynchronously lists SQLite database files in the 'storage/db' directory of a given project repository.
        Args:
            project_id (str): The unique identifier of the project whose DB files are to be listed.
        Returns:
            list[dict] or Response: 
                - On success: A list of dictionaries, each containing the 'name' and 'path' of a SQLite database file (.sqlite or .sqlite3) found in the directory.
                - On failure: An error response with appropriate status code and message.
        Raises:
            Exception: Logs and returns an error response if any unexpected exception occurs during the process.
        Notes:
            - Uses the Gitea API to fetch the contents of the 'storage/db' directory.
            - Handles cases where the directory does not exist or the API request fails.
        """
        
        try:
            url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/storage/db"
            response = requests.get(url)

            if response.status_code == 404:
                return error_response(
                    status_code=status.HTTP_404_NOT_FOUND,
                    message="DB directory not found",
                    detail="storage/db does not exist in this project",
                )

            if response.status_code != 200:
                return error_response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="Failed to fetch DB directory",
                    detail=response.text,
                )

            contents = response.json()
            db_files = [
                {
                    "name": item["name"],
                    "path": item["path"]
                }
                for item in contents
                if item["type"] == "file" and (item["name"].endswith(".sqlite") or item["name"].endswith(".sqlite3"))
            ]

            return db_files

        except Exception as e:
            logger.error(f"Error listing DB files: {str(e)}")
            return error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Error listing DB files",
                detail=str(e),
            )

    @staticmethod
    async def get_tables_in_db(project_id: str, db_filename: str):
        """
        Retrieves the list of table names from a SQLite database file stored in a remote repository.
        Args:
            project_id (str): The unique identifier of the project in the repository.
            db_filename (str): The name of the SQLite database file to fetch and inspect.
        Returns:
            list[str]: A list of table names in the database if successful.
            OR
            JSONResponse: An error response with appropriate status code and message if the file is not found
                          or if there is a failure in fetching or reading the database.
        Raises:
            Exception: If any unexpected error occurs during the process, an error response is returned and the error is logged.
        Notes:
            - The database file is fetched from a remote repository using the Gitea API.
            - The file content is expected to be base64 encoded.
            - The database is temporarily written to disk for inspection.
        """
        
        try:
            file_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/storage/db/{db_filename}"
            response = requests.get(file_url)

            if response.status_code == 404:
                return error_response(
                    status_code=status.HTTP_404_NOT_FOUND,
                    message=f"{db_filename} not found",
                    detail="This DB file does not exist.",
                )

            if response.status_code != 200:
                return error_response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="Failed to fetch DB file",
                    detail=response.text,
                )

            db_content_base64 = response.json().get("content", "").replace("\n", "")
            db_bytes = base64.b64decode(db_content_base64)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite3") as tmp:
                tmp.write(db_bytes)
                temp_path = tmp.name

            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()

            return tables

        except Exception as e:
            logger.error(f"Error reading DB tables: {str(e)}")
            return error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Failed to read DB tables",
                detail=str(e),
            )
    @staticmethod
    async def get_table_rows(project_id: str, db_filename: str, table_name: str, limit: int = 50):
        """
        Fetches rows from a specified table in a SQLite database file stored in a remote Gitea repository.
        This asynchronous function downloads the database file from the Gitea API, decodes it, and queries the specified table for a limited number of rows. The results are returned as a list of dictionaries, where each dictionary represents a row with column names as keys.
        Args:
            project_id (str): The ID of the project in the Gitea repository.
            db_filename (str): The name of the SQLite database file to fetch.
            table_name (str): The name of the table to query.
            limit (int, optional): The maximum number of rows to return. Defaults to 50.
        Returns:
            list[dict]: A list of dictionaries representing the table rows if successful.
            OR
            JSONResponse: An error response with appropriate status code and message if the file is not found or another error occurs.
        Raises:
            Exception: If there is an error reading the table rows or fetching the database file.
        """
        

        try:
            file_url = f"{settings.GITEA_API_URL}/repos/CodeBeGen/{project_id}/contents/storage/db/{db_filename}"
            response = requests.get(file_url)

            if response.status_code == 404:
                return error_response(
                    status_code=status.HTTP_404_NOT_FOUND,
                    message=f"{db_filename} not found",
                    detail="This DB file does not exist.",
                )

            if response.status_code != 200:
                return error_response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="Failed to fetch DB file",
                    detail=response.text,
                )

            db_content_base64 = response.json().get("content", "").replace("\n", "")
            db_bytes = base64.b64decode(db_content_base64)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite3") as tmp:
                tmp.write(db_bytes)
                temp_path = tmp.name

            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()

            query = f"SELECT * FROM `{table_name}` LIMIT {limit};"
            cursor.execute(query)

            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            conn.close()

            # Return as list of dicts
            results = [dict(zip(columns, row)) for row in rows]
            return results

        except Exception as e:
            logger.error(f"Error reading table rows: {str(e)}")
            return error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Failed to read table rows",
                detail=str(e),
            )

    @staticmethod
    async def get_full_db_view(project_id: str, row_limit: int = 10):
        """
        Asynchronously retrieves a comprehensive view of all databases associated with a given project, 
        including their tables and a limited number of rows from each table.
        Args:
            project_id (str): The unique identifier of the project whose databases are to be viewed.
            row_limit (int, optional): The maximum number of rows to retrieve from each table. Defaults to 10.
        Returns:
            list: A list of dictionaries, each representing a database file with its name, path, 
                  and a list of tables (each containing the table name and its rows).
            JSONResponse: If an error occurs or if the project databases/tables cannot be retrieved, 
                          returns a JSONResponse with the appropriate error message.
        Raises:
            Exception: Logs and returns an error response if any unexpected exception occurs during processing.
        """
        
        try:
            db_files = await GetProjectDatabases.list_db_files(project_id)
            if isinstance(db_files, JSONResponse):
                return db_files

            result = []

            for db_file in db_files:
                db_filename = db_file["name"]
                tables = await GetProjectDatabases.get_tables_in_db(project_id, db_filename)

                if isinstance(tables, JSONResponse):
                    tables = []

                tables_data = []

                for table_name in tables:
                    rows = await GetProjectDatabases.get_table_rows(project_id, db_filename, table_name, row_limit)
                    if isinstance(rows, JSONResponse):
                        rows = []

                    tables_data.append({
                        "name": table_name,
                        "rows": rows
                    })

                result.append({
                    "db_file": db_filename,
                    "path": db_file["path"],
                    "tables": tables_data
                })

            return result

        except Exception as e:
            logger.error(f"Error getting full DB view: {str(e)}")
            return error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Error generating full DB view",
                detail=str(e),
            )
