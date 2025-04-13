import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from app.api.v1.schemas.code_generation import (
    CodeGenerationRequest,
    CodeGenerationResponse,
    GenerationResult,
)
from app.api.v1.services.git_service import GitService
from app.api.v1.services.langchain_service import LangchainService
from app.api.v1.services.llm_service import LLMService
from app.api.v1.utils.entity_extractor import extract_entity_from_code

logger = logging.getLogger(__name__)

# Define callback type hints
EventCallback = Callable[[str, Any], Awaitable[None]]
InfoCallback = Callable[[str], Awaitable[None]]


class CodeGenerationService:
    """
    Service for handling code generation requests with intelligent component detection
    and model schema updates.

    Supports event callbacks for streaming progress updates.
    """

    def __init__(
        self,
        on_endpoint_start: Optional[EventCallback] = None,
        on_endpoint_complete: Optional[EventCallback] = None,
        on_model_start: Optional[EventCallback] = None,
        on_model_complete: Optional[EventCallback] = None,
        on_schema_start: Optional[EventCallback] = None,
        on_schema_complete: Optional[EventCallback] = None,
        on_helpers_start: Optional[EventCallback] = None,
        on_helpers_complete: Optional[EventCallback] = None,
        on_migration_start: Optional[EventCallback] = None,
        on_migration_complete: Optional[EventCallback] = None,
        on_info: Optional[InfoCallback] = None,
    ):
        """
        Initialize the service with optional event callbacks.

        Args:
            on_endpoint_start: Called when endpoint generation starts
            on_endpoint_complete: Called when endpoint generation completes
            on_model_start: Called when model generation starts
            on_model_complete: Called when model generation completes
            on_schema_start: Called when schema generation starts
            on_schema_complete: Called when schema generation completes
            on_helpers_start: Called when helpers generation starts
            on_helpers_complete: Called when helpers generation completes
            on_migration_start: Called when migration generation starts
            on_migration_complete: Called when migration generation completes
            on_info: Called for general information messages
        """
        self.on_endpoint_start = on_endpoint_start
        self.on_endpoint_complete = on_endpoint_complete
        self.on_model_start = on_model_start
        self.on_model_complete = on_model_complete
        self.on_schema_start = on_schema_start
        self.on_schema_complete = on_schema_complete
        self.on_helpers_start = on_helpers_start
        self.on_helpers_complete = on_helpers_complete
        self.on_migration_start = on_migration_start
        self.on_migration_complete = on_migration_complete
        self.on_info = on_info

    async def _notify_event(
        self, callback: Optional[EventCallback], event_name: str, data: Any
    ):
        """Helper method to call a callback if it exists"""
        if callback:
            try:
                await callback(event_name, data)
            except Exception as e:
                logger.error(f"Error in callback {event_name}: {str(e)}")

    async def _notify_info(self, message: str):
        """Helper method to call the info callback if it exists"""
        if self.on_info:
            try:
                await self.on_info(message)
            except Exception as e:
                logger.error(f"Error in info callback: {str(e)}")

    async def generate_endpoint(
        self,
        project_id: str,
        endpoint_description: str,
        method: str,
        endpoint_path: str,
        language: str = "python",
        additional_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate endpoint code with event notifications"""
        try:
            # Notify endpoint generation start
            await self._notify_event(
                self.on_endpoint_start,
                "endpoint",
                {
                    "description": endpoint_description,
                    "method": method,
                    "path": endpoint_path,
                },
            )

            # Generate the endpoint
            result = await LangchainService.generate_endpoint(
                project_id=project_id,
                endpoint_description=endpoint_description,
                method=method,
                endpoint_path=endpoint_path,
                language=language,
                additional_context=additional_context,
            )

            # Notify endpoint generation complete
            await self._notify_event(self.on_endpoint_complete, "endpoint", result)

            return result
        except Exception as e:
            logger.error(f"Error generating endpoint: {str(e)}", exc_info=True)
            raise

    async def generate_model(
        self,
        project_id: str,
        entity_name: str,
        entity_description: str,
        language: str = "python",
        endpoint_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate model code with event notifications"""
        try:
            # Notify model generation start
            await self._notify_event(
                self.on_model_start, "model", {"entity_name": entity_name}
            )

            # Generate the model
            result = await LangchainService.generate_model(
                project_id=project_id,
                entity_name=entity_name,
                entity_description=entity_description,
                language=language,
                endpoint_code=endpoint_code,
            )

            # Notify model generation complete
            await self._notify_event(self.on_model_complete, "model", result)

            return result
        except Exception as e:
            logger.error(f"Error generating model: {str(e)}", exc_info=True)
            raise

    async def generate_schema(
        self,
        project_id: str,
        entity_name: str,
        language: str = "python",
        endpoint_code: Optional[str] = None,
        model_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate schema code with event notifications"""
        try:
            # Notify schema generation start
            await self._notify_event(
                self.on_schema_start, "schema", {"entity_name": entity_name}
            )

            # Generate the schema
            result = await LangchainService.generate_schema(
                project_id=project_id,
                entity_name=entity_name,
                language=language,
                endpoint_code=endpoint_code,
                model_code=model_code,
            )

            # Notify schema generation complete
            await self._notify_event(self.on_schema_complete, "schema", result)

            return result
        except Exception as e:
            logger.error(f"Error generating schema: {str(e)}", exc_info=True)
            raise

    async def generate_migration(
        self,
        project_id: str,
        entity_name: str,
        language: str = "python",
        model_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate migration code with event notifications"""
        try:
            # Notify migration generation start
            await self._notify_event(
                self.on_migration_start, "migration", {"entity_name": entity_name}
            )

            # Generate the migration
            result = await LangchainService.generate_migration(
                project_id=project_id,
                entity_name=entity_name,
                language=language,
                model_code=model_code,
            )

            # Notify migration generation complete
            await self._notify_event(self.on_migration_complete, "migration", result)

            return result
        except Exception as e:
            logger.error(f"Error generating migration: {str(e)}", exc_info=True)
            raise

    async def generate_helpers(
        self,
        project_id: str,
        entity_name: str,
        entity_description: str,
        language: str = "python",
        endpoint_code: Optional[str] = None,
        model_code: Optional[str] = None,
        schema_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate helper functions with event notifications"""
        try:
            # Notify helpers generation start
            await self._notify_event(
                self.on_helpers_start, "helpers", {"entity_name": entity_name}
            )

            # Generate the helpers
            result = await LangchainService.generate_helpers(
                project_id=project_id,
                entity_name=entity_name,
                entity_description=entity_description,
                language=language,
                endpoint_code=endpoint_code,
                model_code=model_code,
                schema_code=schema_code,
            )

            # Notify helpers generation complete
            await self._notify_event(self.on_helpers_complete, "helpers", result)

            return result
        except Exception as e:
            logger.error(f"Error generating helpers: {str(e)}", exc_info=True)
            raise

    async def generate_code(
        self, request: CodeGenerationRequest
    ) -> CodeGenerationResponse:
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
            endpoint_path = (
                request.endpoint_path or f"/api/{prompt.lower().replace(' ', '-')}"
            )

            logger.info(f"Generating code in {language} for: {prompt}")
            await self._notify_info(
                f"Starting code generation in {language} for: {prompt}"
            )

            # Generate the endpoint code
            endpoint_result = await self.generate_endpoint(
                project_id=project_id,
                endpoint_description=prompt,
                method=method,
                endpoint_path=endpoint_path,
                language=language,
                additional_context=request.additional_context,
            )

            # Check if the endpoint needs models and schemas
            needs_models = LLMService.needs_model_and_schema(
                endpoint_result.get("generated_code", "")
            )

            logger.info(f"Endpoint analysis result: needs_models={needs_models}")
            await self._notify_info(
                f"Analysis complete. Database components needed: {needs_models}"
            )

            result = {
                "endpoint": endpoint_result,
                "language": language,
                "file_extension": LangchainService.get_file_extension(language),
            }

            # If the endpoint needs models, generate them
            if needs_models:
                logger.info("Generating additional components (model, schema, helpers)")
                await self._notify_info(
                    "Generating additional components (model, schema, helpers)"
                )

                # Extract entity name from the endpoint code
                entity_name = (
                    extract_entity_from_code(
                        endpoint_result.get("generated_code", ""), language
                    )
                    or "User"
                )

                logger.info(f"Using entity name: {entity_name}")
                await self._notify_info(f"Using entity name: {entity_name}")

                # First, check if the entity already exists and needs updates
                update_result = await self._check_and_update_existing_model(
                    project_id,
                    entity_name,
                    prompt,
                    endpoint_result.get("generated_code", ""),
                    language,
                )

                if update_result and update_result.get("model_updated", False):
                    # Model exists and was updated
                    logger.info(
                        f"Updated existing model {entity_name} with fields: {update_result.get('field_changes', {}).get('added_fields', [])}"
                    )
                    await self._notify_info(f"Updated existing model {entity_name}")

                    # Add update results to our response
                    result["model"] = {
                        "exists": True,
                        "updated": True,
                        "entity_name": entity_name,
                        "file_path": update_result.get("model_file"),
                        "generated_code": update_result.get("content_base64"),
                        "update_details": update_result.get("field_changes"),
                    }

                    # Add schema update results if applicable
                    if update_result.get("schema_updated", False):
                        schema_results = update_result.get("schema_results", [])
                        result["schema"] = {
                            "exists": True,
                            "updated": True,
                            "entity_name": entity_name,
                            "schema_details": schema_results,
                        }
                    else:
                        result["schema"] = {
                            "exists": True,
                            "updated": False,
                            "entity_name": entity_name,
                        }

                    # Add migration if it was generated during the update
                    if update_result.get("migration"):
                        result["migration"] = update_result.get("migration")

                    # Process files to commit from the update
                    if update_result.get("files_to_commit"):
                        await self._commit_updated_files(
                            project_id, update_result.get("files_to_commit")
                        )

                    result["entity_name"] = entity_name
                    result["detected_database_usage"] = needs_models

                else:
                    # Model doesn't exist or no updates needed, generate as usual
                    await self._notify_info(f"Generating new model for {entity_name}")

                    model_result = await self.generate_model(
                        project_id=project_id,
                        entity_name=entity_name,
                        entity_description=prompt,
                        language=language,
                        endpoint_code=endpoint_result.get("generated_code", ""),
                    )
                    result["model"] = model_result

                    schema_result = await self.generate_schema(
                        project_id=project_id,
                        entity_name=entity_name,
                        language=language,
                        endpoint_code=endpoint_result.get("generated_code", ""),
                        model_code=model_result.get("generated_code", ""),
                    )
                    result["schema"] = schema_result

                    # Generate migration based on the model
                    migration_result = await self.generate_migration(
                        project_id=project_id,
                        entity_name=entity_name,
                        language=language,
                        model_code=model_result.get("generated_code", ""),
                    )
                    result["migration"] = migration_result

                    schema_code = schema_result.get("generated_code", "")
                    helpers_result = await self.generate_helpers(
                        project_id=project_id,
                        entity_name=entity_name,
                        entity_description=prompt,
                        language=language,
                        endpoint_code=endpoint_result.get("generated_code", ""),
                        model_code=model_result.get("generated_code", ""),
                        schema_code=schema_code,
                    )
                    result["helpers"] = helpers_result

                    result["entity_name"] = entity_name
                    result["detected_database_usage"] = needs_models

                    # Commit all generated files to git
                    git_results = await self._commit_files_to_git(project_id, result)
                    result["git_results"] = git_results
            else:
                # If no models needed, just commit the endpoint
                git_results = await self._commit_files_to_git(project_id, result)
                result["git_results"] = git_results

            await self._notify_info("Code generation completed successfully")
            generation_result = GenerationResult(**result)

            return CodeGenerationResponse(
                success=True,
                message="Code generation successful",
                result=generation_result,
            )

        except Exception as e:
            error_msg = f"Error in code generation for project '{request.project_id}' and prompt '{request.prompt}': {e}"
            logger.error(error_msg, exc_info=True)
            await self._notify_info(f"Error in code generation: {str(e)}")

            return CodeGenerationResponse(
                success=False,
                message=f"Error in code generation: {str(e)}",
                result=None,
            )

    # The following methods remain unchanged from your original implementation
    async def _check_and_update_existing_model(
        self, project_id, entity_name, prompt_description, endpoint_code, language
    ):
        """Check if entity already exists and update it if needed"""
        try:
            # First check if there's an existing model
            from app.api.v1.services.project_analysis_service import (
                ProjectAnalysisService,
            )

            project_analysis = await ProjectAnalysisService.analyze_project(project_id)

            # Use LLMService's helper to find existing model
            existing_model = LLMService._find_existing_model(
                entity_name, project_analysis.get("models", [])
            )

            if not existing_model:
                logger.info(
                    f"No existing model found for {entity_name}, will generate new components"
                )
                return None

            logger.info(
                f"Found existing model for entity {entity_name}, analyzing potential updates"
            )

            # Use ModelSchemaManager to analyze and process model changes
            from app.api.v1.services.model_schema_update_service import (
                ModelSchemaManager,
            )

            update_result = await ModelSchemaManager.process_model_changes(
                project_id=project_id,
                entity_name=entity_name,
                prompt_description=prompt_description,
                endpoint_code=endpoint_code,
                generate_migration=False,  # Don't generate migration automatically
                language=language,
            )

            # Only generate migration if changes were actually made
            if update_result and update_result.get("model_updated", False):
                logger.info("Model was updated, generating migration")
                # Generate migration explicitly

                migration_result = await LangchainService.generate_migration(
                    project_id=project_id,
                    entity_name=entity_name,
                    language=language,
                    model_code=update_result.get("content_base64", None),
                )

                # Add migration to files to commit if generated successfully
                if migration_result and "generated_code" in migration_result:
                    logger.info(
                        f"Adding migration to commit: {migration_result.get('file_path')}"
                    )
                    if "files_to_commit" not in update_result:
                        update_result["files_to_commit"] = []

                    update_result["files_to_commit"].append(
                        {
                            "file_path": migration_result.get("file_path"),
                            "commit_message": f"feat: Add migration for {entity_name} model changes",
                            "content": migration_result.get("generated_code"),
                        }
                    )

                    update_result["migration"] = migration_result
            else:
                logger.info(
                    "No changes were made to the model, skipping migration generation"
                )

            return update_result

        except Exception as e:
            logger.error(f"Error checking for existing model: {str(e)}", exc_info=True)
            return None

    async def _commit_updated_files(self, project_id, files_to_commit):
        """Commit updated files to Git repository"""
        # Keep the implementation as is
        commit_results = {}

        try:
            for file_info in files_to_commit:
                file_path = file_info.get("file_path")
                content = file_info.get("content")
                commit_message = file_info.get("commit_message")

                if not file_path or not content:
                    logger.warning(
                        f"Skipping commit for file with missing path or content: {file_path}"
                    )
                    continue

                logger.info(f"Committing updated file: {file_path}")
                commit_result = await GitService.commit_file_update(
                    project_id=project_id,
                    new_code=content,
                    file_path=file_path,
                    commit_message=commit_message or f"Update {file_path}",
                )

                commit_results[file_path] = commit_result

            return commit_results

        except Exception as e:
            logger.error(f"Error committing updated files: {str(e)}", exc_info=True)
            return {"error": str(e)}

    async def _commit_files_to_git(self, project_id, generation_result):
        """Commit all generated files to Git repository"""
        # Keep the implementation as is
        git_results = {}

        try:
            endpoint = generation_result.get("endpoint", {})
            endpoint_commit = await GitService.commit_file_update(
                project_id=project_id,
                new_code=endpoint.get("generated_code", ""),
                file_path=endpoint.get("file_path", ""),
                commit_message=f"Add {endpoint.get('method', 'GET')} endpoint for {endpoint.get('endpoint_path', '')}",
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
                    commit_message=f"Add {model.get('entity_name', 'Entity')} model",
                )
                git_results["model"] = model_commit

                schema = generation_result.get("schema", {})
                schema_commit = await GitService.commit_file_update(
                    project_id=project_id,
                    new_code=schema.get("generated_code", ""),
                    file_path=schema.get("file_path", ""),
                    commit_message=f"Add {schema.get('entity_name', 'Entity')} schema",
                )
                git_results["schema"] = schema_commit

                # Commit migration if it exists
                migration = generation_result.get("migration", {})
                if migration and migration.get("generated_code"):
                    migration_commit = await GitService.commit_file_update(
                        project_id=project_id,
                        new_code=migration.get("generated_code", ""),
                        file_path=migration.get("file_path", ""),
                        commit_message=f"Add migration for {migration.get('entity_name', 'Entity')} model",
                    )
                    git_results["migration"] = migration_commit
                    logger.info(
                        f"Committed migration file: {migration.get('file_path')}"
                    )
            except Exception as e:
                logger.error(f"Failed to commit model/schema/migration: {e}")

        try:
            helpers = generation_result.get("helpers", {})
            helpers_commit = await GitService.commit_file_update(
                project_id=project_id,
                new_code=helpers.get("generated_code", ""),
                file_path=helpers.get("file_path", ""),
                commit_message=f"Add helper functions for {helpers.get('entity_name', 'Entity')}",
            )
            git_results["helpers"] = helpers_commit
        except Exception as e:
            logger.error(f"Failed to commit helpers: {e}")

        return git_results
