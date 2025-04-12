from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, status
from typing import Dict, Any
import json
import logging
import os
from app.api.v1.services.langchain_service import LangchainService
from app.api.v1.utils.streaming_callback import StreamingCallback
from app.api.v1.utils.prompt_manager import PromptManager

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws/generate/{artifact_type}")
async def generate_artifact_stream(
    websocket: WebSocket,
    artifact_type: str,
):
    """WebSocket endpoint for streaming code generation"""
    await websocket.accept()
    
    try:
        # Get parameters from the client
        data = await websocket.receive_text()
        params = json.loads(data)
        
        # Extract common parameters
        language = params.get("language", "python").lower()
        project_id = params.get("project_id", "default")
        
        # Create a streaming callback
        callback = StreamingCallback(websocket=websocket)
        
        # Process based on artifact type
        if artifact_type == "endpoint":
            # Get and format the appropriate template
            template = PromptManager.format_template(
                "endpoint",
                language=language,
                endpoint_description=params.get("endpoint_description", ""),
                method=params.get("method", "GET"),
                method_lower=params.get("method", "GET").lower(),
                endpoint_path=params.get("endpoint_path", "/"),
                additional_context=params.get("additional_context", "")
            )
            
            # Create a streaming chain
            chain = LangchainService.create_streaming_chain(template, callback)
            
            # Execute the chain
            await chain.ainvoke({"input": params.get("endpoint_description", "")})
            
        elif artifact_type == "model":
            # Get and format the appropriate template
            template = PromptManager.format_template(
                "model",
                language=language,
                entity_name=params.get("entity_name", ""),
                entity_description=params.get("entity_description", ""),
                endpoint_code=params.get("endpoint_code", "# Endpoint code not provided")
            )
            
            # Create a streaming chain
            chain = LangchainService.create_streaming_chain(template, callback)
            
            # Execute the chain
            await chain.ainvoke({"input": params.get("entity_description", "")})
            
        elif artifact_type == "schema":
            # Get and format the appropriate template
            template = PromptManager.format_template(
                "schema",
                language=language,
                entity_name=params.get("entity_name", ""),
                endpoint_code=params.get("endpoint_code", "# Endpoint code not provided"),
                model_code=params.get("model_code", "# Model code not provided")
            )
            
            # Create a streaming chain
            chain = LangchainService.create_streaming_chain(template, callback)
            
            # Execute the chain
            await chain.ainvoke({"input": params.get("entity_name", "")})
            
        elif artifact_type == "migration":
            # Determine the latest migration ID
            from app.api.v1.utils.migration_finder import get_latest_migration_id
            project_path = f"repos/{project_id}"
            alembic_dir = os.path.join(project_path, "alembic")
            latest_migration_id = get_latest_migration_id(alembic_dir=alembic_dir)
            
            # Get and format the appropriate template
            template = PromptManager.format_template(
                "migration",
                language=language,
                entity_name=params.get("entity_name", ""),
                latest_migration_id=latest_migration_id,
                model_code=params.get("model_code", "# Model code not provided")
            )
            
            # Create a streaming chain
            chain = LangchainService.create_streaming_chain(template, callback)
            
            # Execute the chain
            await chain.ainvoke({"input": params.get("entity_name", "")})
            
        elif artifact_type == "helpers":
            # Get and format the appropriate template
            template = PromptManager.format_template(
                "helpers",
                language=language,
                entity_name=params.get("entity_name", ""),
                entity_description=params.get("entity_description", ""),
                endpoint_code=params.get("endpoint_code", "# Endpoint code not provided"),
                model_code=params.get("model_code", "# Model code not provided"),
                schema_code=params.get("schema_code", "# Schema code not provided")
            )
            
            # Create a streaming chain
            chain = LangchainService.create_streaming_chain(template, callback)
            
            # Execute the chain
            await chain.ainvoke({"input": params.get("entity_description", "")})
            
        else:
            await websocket.send_json({
                "status": "error",
                "message": f"Unsupported artifact type: {artifact_type}"
            })
            return
        
        # Send completion message with file extension info
        file_extension = LangchainService.get_file_extension(language)
        await websocket.send_json({
            "status": "complete",
            "code": callback.get_content(),
            "language": language,
            "file_extension": file_extension
        })
    
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in streaming endpoint: {str(e)}", exc_info=True)
        try:
            await websocket.send_json({
                "status": "error",
                "message": str(e)
            })
        except:
            logger.error("Could not send error message to client - connection may be closed")