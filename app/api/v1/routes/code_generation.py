import logging
import json
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status

from app.api.v1.utils.success_response import success_response
from app.api.v1.utils.error_response import error_response
from app.api.v1.services.code_generation import CodeGenerationService
from app.api.v1.schemas.code_generation import CodeGenerationRequest, CodeGenerationResponse

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/generate", response_model=CodeGenerationResponse, status_code=status.HTTP_200_OK)
async def generate_code(request: CodeGenerationRequest):
    """
    Generate code based on user description.
    
    This unified endpoint handles all code generation requests.
    The system will intelligently determine what needs to be generated based on the prompt.
    
    - Parameters:
      - project_id: Identifier for the project
      - prompt: Natural language description of what should be generated
      - language: Target programming language (python, javascript, etc.)
      - method: HTTP method for endpoint generation (GET, POST, etc.) if applicable
      - endpoint_path: Path for the endpoint if applicable
      - additional_context: Optional context about the project or requirements
      
    - Returns:
      All generated code components (endpoint, model, schema, etc.) as appropriate
    """
    try:
        # Create an instance of CodeGenerationService
        code_gen_service = CodeGenerationService()
        
        # Call the generate_code method on the instance
        result = await code_gen_service.generate_code(request)
        return result
    except Exception as e:
        logger.error(f"Error in code generation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code generation failed: {str(e)}"
        )

@router.websocket("/generate/stream")
async def generate_code_stream(websocket: WebSocket):
    """
    Stream code generation results as they're being generated.
    
    This WebSocket endpoint provides real-time streaming of generated code.
    The system will intelligently determine what needs to be generated based on the prompt.
    
    The client should send a JSON message with the same structure as the CodeGenerationRequest.
    The server will respond with streaming updates as each component is generated.
    """
    await websocket.accept()
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "status": "connected", 
            "message": "WebSocket connection established"
        })
        
        # Receive the request parameters as JSON
        data = await websocket.receive_text()
        params = json.loads(data)
        
        # Log the received data
        logger.info(f"Received streaming request: {params}")
        
        # Convert to request object for validation
        try:
            request = CodeGenerationRequest(**params)
        except Exception as e:
            logger.error(f"Invalid request parameters: {str(e)}")
            await websocket.send_json({
                "status": "error",
                "message": f"Invalid request parameters: {str(e)}"
            })
            await websocket.close()
            return
        
        # Define callback handlers for the CodeGenerationService
        async def on_component_start(component_type, data):
            entity_name = data.get("entity_name", "")
            message = f"Generating {component_type} for entity: {entity_name}" if entity_name else f"Generating {component_type}..."
            
            await websocket.send_json({
                "status": "progress",
                "stage": component_type,
                "message": message
            })
        
        async def on_component_complete(component_type, result):
            await websocket.send_json({
                "status": "completed",
                "stage": component_type,
                "result": result
            })
        
        async def on_info(message):
            await websocket.send_json({
                "status": "info",
                "message": message
            })
        
        # Create an instance of CodeGenerationService with WebSocket callbacks
        code_gen_service = CodeGenerationService(
            on_endpoint_start=lambda event, data: on_component_start("endpoint", data),
            on_endpoint_complete=lambda event, data: on_component_complete("endpoint", data),
            on_model_start=lambda event, data: on_component_start("model", data),
            on_model_complete=lambda event, data: on_component_complete("model", data),
            on_schema_start=lambda event, data: on_component_start("schema", data),
            on_schema_complete=lambda event, data: on_component_complete("schema", data),
            on_helpers_start=lambda event, data: on_component_start("helpers", data),
            on_helpers_complete=lambda event, data: on_component_complete("helpers", data),
            on_migration_start=lambda event, data: on_component_start("migration", data),
            on_migration_complete=lambda event, data: on_component_complete("migration", data),
            on_info=on_info
        )
        
        # Generate the code using the same service as the regular endpoint
        response = await code_gen_service.generate_code(request)
        
        # Send the final complete message
        await websocket.send_json({
            "status": "complete",
            "message": "Code generation completed successfully",
            "result": response.result.dict() if response.success and response.result else None
        })
    
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected during code generation")
    except Exception as e:
        logger.error(f"Error in streaming code generation: {str(e)}", exc_info=True)
        # Try to send error message if the connection is still open
        try:
            await websocket.send_json({
                "status": "error",
                "message": f"Code generation failed: {str(e)}"
            })
        except:
            pass 