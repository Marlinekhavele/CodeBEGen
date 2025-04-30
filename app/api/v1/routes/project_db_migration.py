import logging
from datetime import datetime
from fastapi import APIRouter, status, WebSocket
from fastapi.responses import StreamingResponse
from app.api.v1.schemas.project_db_migration import (
    MigrationRunData,
    MigrationRunSuccessResponse,
)
from app.api.v1.services.language_templates import LanguageTemplateFactory
from app.api.v1.utils.endpoint_services import get_project_dir_from_repo_url
from app.api.v1.utils.error_response import error_response
from app.api.v1.utils.git_utils import get_repo_url
from app.api.v1.utils.success_response import success_response
import asyncio
import json

logger = logging.getLogger(__name__)
router = APIRouter(tags=["migration of database"])


@router.post(
    "/migration/{project_id}/run",
    response_model=MigrationRunSuccessResponse,
    status_code=status.HTTP_200_OK,
)
async def run_migrations(project_id: str):
    """
    Applies pending database migrations for the specified project.

    This endpoint runs all pending Alembic migrations for a project without generating new ones.
    It's intended to be called separately after code generation when the user is ready to apply
    database changes.

    Args:
        project_id (str): The project identifier

    Returns:
        MigrationRunSuccessResponse: Result of the migration operation including success status and message

    Raises:
        HTTPException: If migrations cannot be applied or the project is not found
    """
    try:
        # Get project_id
        repo_url = get_repo_url(project_id)
        if not repo_url:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Project not found",
                detail=f"No repository found for project ID: {project_id}",
            )

        project_dir = get_project_dir_from_repo_url(repo_url)

        # Create a PythonTemplate instance
        language_template = LanguageTemplateFactory.get_template("python")

        # Run the migrations
        result = await language_template.run_migrations(project_dir)

        # Prepare response data
        migration_data = MigrationRunData(
            success=result.get("success", False),
            message=result.get("message", "Migration execution completed"),
            database_path=result.get("database_path"),
        )
        # Check if migration was actually successful
        if not migration_data.success:
            return error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Migration execution failed",
                detail=migration_data.message,
            )
        # Return success response
        return success_response(
            status_code=status.HTTP_200_OK,
            message="Migration execution completed",
            data=migration_data,
        )

    except ValueError as e:
        # Handle specific errors like project not found
        return error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            message="Project not found",
            detail=str(e),
        )
    except Exception as e:
        # Log the error and return a server error response
        logger.error(f"Error in run_migrations endpoint: {str(e)}", exc_info=True)
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Migration execution failed",
            detail=str(e),
        )

@router.get(
    "/migration/{project_id}/logs",
    status_code=status.HTTP_200_OK,
)
async def stream_migration_logs(project_id: str):
    """
    Streams migration logs in real-time for the specified project.
    
    Args:
        project_id (str): The project identifier
        
    Returns:
        StreamingResponse: A stream of Server-Sent Events containing log messages
    """
    try:
        # Get project directory
        repo_url = get_repo_url(project_id)
        if not repo_url:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Project not found",
                detail=f"No repository found for project ID: {project_id}",
            )
            
        project_dir = get_project_dir_from_repo_url(repo_url)
        
        # Define the async generator for streaming logs
        async def event_generator():
            # Initial connection message
            timestamp = datetime.now().strftime("%H:%M:%S")
            yield f"data: {json.dumps({'timestamp': timestamp, 'message': f'Starting migration process for project {project_id}', 'level': 'info'})}\n\n"
            
            # Simulate delay for connection setup
            await asyncio.sleep(0.5)
            
            # Log collector function that will be used to capture logs
            log_queue = asyncio.Queue()
            
            # Function to add a log entry to the queue
            async def add_log(message, level="info"):
                timestamp = datetime.now().strftime("%H:%M:%S")
                await log_queue.put({
                    "timestamp": timestamp,
                    "message": message,
                    "level": level
                })
            
            # Set up log handlers
            class StreamLogHandler:
                @staticmethod
                async def info(message):
                    await add_log(message, "info")
                    
                @staticmethod
                async def error(message):
                    await add_log(message, "error")
                    
                @staticmethod
                async def warning(message):
                    await add_log(message, "warning")
                    
                @staticmethod
                async def debug(message):
                    await add_log(message, "debug")
            
            # Create a log handler instance
            stream_logger = StreamLogHandler()
            
            # Start migration in a background task
            migration_task = asyncio.create_task(
                run_migration_with_logs(project_dir, stream_logger)
            )
            
            # Stream logs as they become available
            while True:
                try:
                    # Check if migration task is done
                    if migration_task.done():
                        # Get the result (or exception)
                        try:
                            result = migration_task.result()
                            # Send final success message
                            await add_log(f"Migration completed: {result.get('message', 'Done')}", 
                                         "success" if result.get("success") else "error")
                        except Exception as e:
                            # Send final error message
                            await add_log(f"Migration failed: {str(e)}", "error")
                        
                        # Process any remaining logs
                        while not log_queue.empty():
                            log_entry = await log_queue.get()
                            yield f"data: {json.dumps(log_entry)}\n\n"
                            
                        # Send completion event
                        yield f"data: {json.dumps({'timestamp': datetime.now().strftime('%H:%M:%S'), 'message': 'Stream completed', 'level': 'info', 'completed': True})}\n\n"
                        break
                    
                    # Get a log entry with timeout
                    try:
                        log_entry = await asyncio.wait_for(log_queue.get(), 0.5)
                        yield f"data: {json.dumps(log_entry)}\n\n"
                    except asyncio.TimeoutError:
                        # No log entry available, just continue
                        continue
                    
                except Exception as e:
                    # Log error and continue
                    logger.error(f"Error while streaming logs: {str(e)}")
                    yield f"data: {json.dumps({'timestamp': datetime.now().strftime('%H:%M:%S'), 'message': f'Error while streaming logs: {str(e)}', 'level': 'error'})}\n\n"
                    await asyncio.sleep(1)
            
        # Return the streaming response
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream"
        )
        
    except Exception as e:
        logger.error(f"Error setting up log stream: {str(e)}", exc_info=True)
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to set up migration log stream",
            detail=str(e),
        )

# Helper function to run migration with log streaming
async def run_migration_with_logs(project_dir, logger):
    """
    Runs the migration process while sending logs to the provided logger.
    
    Args:
        project_dir: Path to the project directory
        logger: Logger object with async methods for logging
        
    Returns:
        dict: The migration result
    """
    try:
        # Create a language template instance
        language_template = LanguageTemplateFactory.get_template("python")
        
        # Modify your migration function to accept a logger for streaming logs
        # This requires changes to your language_template.run_migrations method
        result = await language_template.run_migrations_with_logs(project_dir, logger)
        
        return result
        
    except Exception as e:
        await logger.error(f"Error during migration: {str(e)}")
        raise

# Helper function to run migration with log streaming
async def run_migration_with_logs(project_dir, logger):
    """
    Runs the migration process while sending logs to the provided logger.
    
    Args:
        project_dir: Path to the project directory
        logger: Logger object with async methods for logging
        
    Returns:
        dict: The migration result
    """
    try:
        # Create a language template instance
        language_template = LanguageTemplateFactory.get_template("python")
        
        # Modify your migration function to accept a logger for streaming logs
        # This requires changes to your language_template.run_migrations method
        result = await language_template.run_migrations_with_logs(project_dir, logger)
        
        return result
        
    except Exception as e:
        await logger.error(f"Error during migration: {str(e)}")
        raise    