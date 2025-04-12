import logging
from typing import Dict, Any, Optional
from app.api.v1.services.git_service import GitService
from app.api.v1.services.langchain_service import LangchainService
from app.api.v1.services.llm_service import LLMService
from app.api.v1.schemas.code_generation import (
    CodeGenerationRequest,
    CodeGenerationResponse,
    GenerationResult
)
from app.api.v1.utils.entity_extractor import extract_entity_from_code

logger = logging.getLogger(__name__)

class CodeGenerationService:
    """
    Service for handling code generation requests with intelligent component detection.
    """

    async def generate_code(self, request: CodeGenerationRequest) -> CodeGenerationResponse:
        """
        Generate code based on the request, intelligently determining needed components.

        Args:
            request: The code generation request containing the prompt and options

        Returns:
            A response with the generated code and metadata
        """
        try:
            project_id = request.project_id
            prompt = request.prompt
            language = request.language.lower() if request.language else "python"
            method = request.method or "GET"
            endpoint_path = request.endpoint_path or f"/api/{prompt.lower().replace(' ', '-')}"

            logger.info(f"Generating code in {language} for: {prompt}")

            endpoint_result = await LangchainService.generate_endpoint(
                project_id=project_id,
                endpoint_description=prompt,
                method=method,
                endpoint_path=endpoint_path,
                language=language,
                additional_context=request.additional_context
            )

            needs_models = LLMService.needs_model_and_schema(endpoint_result.get("generated_code", ""))
            logger.info(f"Endpoint analysis result: needs_models={needs_models}")

            result = {
                "endpoint": endpoint_result,
                "language": language,
                "file_extension": LangchainService.get_file_extension(language)
            }

            if needs_models:
                logger.info("Generating additional components (model, schema, helpers)")

                entity_name = extract_entity_from_code(endpoint_result.get("generated_code", ""), language) or "User"
                logger.info(f"Using entity name: {entity_name}")

                model_result = await LangchainService.generate_model(
                    project_id=project_id,
                    entity_name=entity_name,
                    entity_description=prompt,
                    language=language,
                    endpoint_code=endpoint_result.get("generated_code", "")
                )
                result["model"] = model_result

                schema_result = await LangchainService.generate_schema(
                    project_id=project_id,
                    entity_name=entity_name,
                    language=language,
                    endpoint_code=endpoint_result.get("generated_code", ""),
                    model_code=model_result.get("generated_code", "")
                )
                result["schema"] = schema_result

                schema_code = schema_result.get("generated_code", "")
                helpers_result = await LangchainService.generate_helpers(
                    project_id=project_id,
                    entity_name=entity_name,
                    entity_description=prompt,
                    language=language,
                    endpoint_code=endpoint_result.get("generated_code", ""),
                    model_code=model_result.get("generated_code", ""),
                    schema_code=schema_code
                )
                result["helpers"] = helpers_result

                result["entity_name"] = entity_name
                result["detected_database_usage"] = needs_models

            git_results = await self._commit_files_to_git(project_id, result)
            result["git_results"] = git_results

            generation_result = GenerationResult(**result)

            return CodeGenerationResponse(
                success=True,
                message="Code generation successful",
                result=generation_result
            )

        except Exception as e:
            logger.error(f"Error in code generation for project '{request.project_id}' and prompt '{request.prompt}': {e}", exc_info=True)
            return CodeGenerationResponse(
                success=False,
                message=f"Error in code generation: {str(e)}",
                result=None
            )

    async def _commit_files_to_git(self, project_id: str, generation_result: dict) -> dict:
        """
        Commit all generated files to Git repository.

        Args:
            project_id: The project identifier
            generation_result: The results from code generation

        Returns:
            Dictionary with git commit results
        """
        git_results = {}

        try:
            endpoint = generation_result.get("endpoint", {})
            endpoint_commit = await GitService.commit_file_update(
                project_id=project_id,
                new_code=endpoint.get("generated_code", ""),
                file_path=endpoint.get("file_path", ""),
                commit_message=f"Add {endpoint.get('method', 'GET')} endpoint for {endpoint.get('endpoint_path', '')}"
            )
            git_results["endpoint"] = endpoint_commit
        except Exception as e:
            logger.error(f"Failed to commit endpoint: {e}")

        model = generation_result.get("model")
        if model and not model.get("exists", False):
            try:
                model_commit = await GitService.commit_file_update(
                    project_id=project_id,
                    new_code=model.get("generated_code", ""),
                    file_path=model.get("file_path", ""),
                    commit_message=f"Add {model.get('entity_name', 'Entity')} model"
                )
                git_results["model"] = model_commit

                schema = generation_result.get("schema", {})
                schema_commit = await GitService.commit_file_update(
                    project_id=project_id,
                    new_code=schema.get("generated_code", ""),
                    file_path=schema.get("file_path", ""),
                    commit_message=f"Add {schema.get('entity_name', 'Entity')} schema"
                )
                git_results["schema"] = schema_commit
            except Exception as e:
                logger.error(f"Failed to commit model/schema: {e}")

        try:
            helpers = generation_result.get("helpers", {})
            helpers_commit = await GitService.commit_file_update(
                project_id=project_id,
                new_code=helpers.get("generated_code", ""),
                file_path=helpers.get("file_path", ""),
                commit_message=f"Add helper functions for {helpers.get('entity_name', 'Entity')}"
            )
            git_results["helpers"] = helpers_commit
        except Exception as e:
            logger.error(f"Failed to commit helpers: {e}")

        return git_results
