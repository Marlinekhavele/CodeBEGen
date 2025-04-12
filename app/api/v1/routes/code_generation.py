import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, status

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
        service = CodeGenerationService()
        result = await service.generate_code(request)
        return result
    except Exception as e:
        logger.error(f"Error in code generation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code generation failed: {str(e)}"
        )
