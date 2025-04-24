import json
import logging

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session

from app.api.db.database import get_db
from app.api.v1.schemas.code_generation import (
    CodeGenerationRequest,
    CodeGenerationResponse,
)
from app.api.v1.services.code_generation import CodeGenerationService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/generate", response_model=CodeGenerationResponse, status_code=status.HTTP_200_OK
)
async def generate_code(request: CodeGenerationRequest,db: Session = Depends(get_db)):
    """
    Generates code based on a user-provided natural language description.

    This endpoint receives a CodeGenerationRequest containing a prompt and other optional
    context about the desired output (e.g., endpoint, model, schema, etc.). It delegates
    the generation task to the CodeGenerationService and returns the generated code.

    Args:
        request (CodeGenerationRequest): Request object containing prompt, language, and other parameters.

    Returns:
        CodeGenerationResponse: Object containing the generated code components and metadata.

    Raises:
        HTTPException: If the code generation process fails due to an internal error.
    """
    try:
        code_gen_service = CodeGenerationService()
        result = await code_gen_service.generate_code(request,db)
        return result
    except Exception as e:
        logger.error(f"Error in code generation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code generation failed: {str(e)}",
        )


@router.websocket("/generate/stream")
async def generate_code_stream(websocket: WebSocket, db: Session = Depends(get_db)):
    """
    Streams real-time code generation updates over WebSocket.

    This WebSocket endpoint enables clients to receive progressive updates during
    the code generation process. It accepts a JSON message matching the
    CodeGenerationRequest schema and streams progress and completion messages as
    components are generated.

    Args:
        websocket (WebSocket): The WebSocket connection object.

    Returns:
        None

    Raises:
        WebSocketDisconnect: If the client disconnects during the code generation session.
        Exception: If an unexpected error occurs during code generation.
    """
    await websocket.accept()

    try:
        await websocket.send_json(
            {"status": "connected", "message": "WebSocket connection established"}
        )

        data = await websocket.receive_text()
        params = json.loads(data)
        logger.info(f"Received streaming request: {params}")

        try:
            request = CodeGenerationRequest(**params)
        except Exception as e:
            logger.error(f"Invalid request parameters: {str(e)}")
            await websocket.send_json(
                {"status": "error", "message": f"Invalid request parameters: {str(e)}"}
            )
            await websocket.close()
            return

        async def on_component_start(component_type, data):
            entity_name = data.get("entity_name", "")
            message = (
                f"Generating {component_type} for entity: {entity_name}"
                if entity_name
                else f"Generating {component_type}..."
            )
            await websocket.send_json(
                {"status": "progress", "stage": component_type, "message": message}
            )

        async def on_component_complete(component_type, result):
            await websocket.send_json(
                {"status": "completed", "stage": component_type, "result": result}
            )

        async def on_info(message):
            await websocket.send_json({"status": "info", "message": message})

        code_gen_service = CodeGenerationService(
            on_endpoint_start=lambda event, data: on_component_start("endpoint", data),
            on_endpoint_complete=lambda event, data: on_component_complete(
                "endpoint", data
            ),
            on_model_start=lambda event, data: on_component_start("model", data),
            on_model_complete=lambda event, data: on_component_complete("model", data),
            on_schema_start=lambda event, data: on_component_start("schema", data),
            on_schema_complete=lambda event, data: on_component_complete(
                "schema", data
            ),
            on_helpers_start=lambda event, data: on_component_start("helpers", data),
            on_helpers_complete=lambda event, data: on_component_complete(
                "helpers", data
            ),
            on_migration_start=lambda event, data: on_component_start(
                "migration", data
            ),
            on_migration_complete=lambda event, data: on_component_complete(
                "migration", data
            ),
            on_dockerfile_start=lambda event, data: on_component_start(
                "dockerfile", data
            ),
            on_dockerfile_complete=lambda event, data: on_component_complete(
                "dockerfile", data
            ),
            on_api_docs_start=lambda event, data: on_component_start("api_docs", data),
            on_api_docs_complete=lambda event, data: on_component_complete(
                "api_docs", data
            ),
            on_info=on_info,
        )

        response = await code_gen_service.generate_code(request, db)

        await websocket.send_json(
            {
                "status": "complete",
                "message": "Code generation completed successfully",
                "result": (
                    response.result.dict()
                    if response.success and response.result
                    else None
                ),
            }
        )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected during code generation")
    except Exception as e:
        logger.error(f"Error in streaming code generation: {str(e)}", exc_info=True)
        try:
            await websocket.send_json(
                {"status": "error", "message": f"Code generation failed: {str(e)}"}
            )
        except Exception:
            pass
