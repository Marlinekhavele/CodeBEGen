from typing import Optional

from pydantic import BaseModel, Field


class MigrationRunData(BaseModel):
    """Data model for migration run results."""

    success: bool = Field(
        ..., description="Indicates if the migrations were applied successfully"
    )
    message: str = Field(..., description="Details about the migration execution")
    database_path: Optional[str] = Field(
        None, description="Path to the SQLite database file"
    )


class MigrationRunSuccessResponse(BaseModel):
    """Success response model for migration run endpoint."""

    status_code: int = Field(..., description="HTTP status code")
    message: str = Field(..., description="Response message")
    data: MigrationRunData = Field(..., description="Migration run result data")
