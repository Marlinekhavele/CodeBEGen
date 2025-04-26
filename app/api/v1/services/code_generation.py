import base64
import hashlib
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.db.database import get_db
from app.api.v1.models.endpoints import EndPoint
from app.api.v1.models.projects import Project
from app.api.v1.schemas.code_generation import (
    CodeGenerationRequest,
    CodeGenerationResponse,
    GenerationResult,
)
from app.api.v1.services.git_service import GitService
from app.api.v1.services.langchain_service import LangchainService
from app.api.v1.services.language_templates import LanguageTemplateFactory
from app.api.v1.services.llm_service import LLMService
from app.api.v1.services.model_schema_update.model_schema_manager import (
    ModelSchemaManager,
)
from app.api.v1.services.project_analysis_service import ProjectAnalysisService

logger = logging.getLogger(__name__)

# Define callback type hints
EventCallback = Callable[[str, Any], Awaitable[None]]
InfoCallback = Callable[[str], Awaitable[None]]


class CodeGenerationService:
    """
    Service for handling code generation requests with intelligent component detection
    and model schema updates, supporting multiple programming languages.
    """

    def __init__(
        self,
        on_component_start: Optional[Dict[str, EventCallback]] = None,
        on_component_complete: Optional[Dict[str, EventCallback]] = None,
        on_info: Optional[InfoCallback] = None,
        # Legacy callback parameters (for backward compatibility)
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
        on_dockerfile_start: Optional[EventCallback] = None,
        on_dockerfile_complete: Optional[EventCallback] = None,
        on_api_docs_start: Optional[EventCallback] = None,
        on_api_docs_complete: Optional[EventCallback] = None,
    ):
        """
        Initialize the service with callbacks for progress updates.

        Args:
            on_component_start: Dictionary mapping component types to start callbacks
            on_component_complete: Dictionary mapping component types to complete callbacks
            on_info: Called for general information messages

            # Legacy callbacks (for backward compatibility)
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
            on_dockerfile_start: Called when Dockerfile generation starts
            on_dockerfile_complete: Called when Dockerfile generation completes
            on_api_docs_start: Called when API docs generation starts
            on_api_docs_complete: Called when API docs generation completes
        """
        # Initialize callback dictionaries
        self.on_component_start = on_component_start or {}
        self.on_component_complete = on_component_complete or {}
        self.on_info = on_info

        # Store legacy callbacks for backward compatibility
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
        # Store new Dockerfile and API docs callbacks
        self.on_dockerfile_start = on_dockerfile_start
        self.on_dockerfile_complete = on_dockerfile_complete
        self.on_api_docs_start = on_api_docs_start
        self.on_api_docs_complete = on_api_docs_complete

        # Map legacy callbacks to component callbacks if not provided
        if not on_component_start:
            self._map_legacy_callbacks_to_components()

    def _map_legacy_callbacks_to_components(self):
        """Map legacy callbacks to component callbacks for backward compatibility"""
        legacy_start_mapping = {
            "endpoint": self.on_endpoint_start,
            "controller": self.on_endpoint_start,  # Map JS controller to endpoint
            "model": self.on_model_start,
            "schema": self.on_schema_start,
            "validation": self.on_schema_start,  # Map JS validation to schema
            "helpers": self.on_helpers_start,
            "utils": self.on_helpers_start,  # Map JS utils to helpers
            "migration": self.on_migration_start,
            "route": self.on_endpoint_start,  # Map JS routes to endpoint
            "dockerfile": self.on_dockerfile_start,  # Add Dockerfile mapping
            "api_docs": self.on_api_docs_start,  # Add API docs mapping
        }

        legacy_complete_mapping = {
            "endpoint": self.on_endpoint_complete,
            "controller": self.on_endpoint_complete,
            "model": self.on_model_complete,
            "schema": self.on_schema_complete,
            "validation": self.on_schema_complete,
            "helpers": self.on_helpers_complete,
            "utils": self.on_helpers_complete,
            "migration": self.on_migration_complete,
            "route": self.on_endpoint_complete,
            "dockerfile": self.on_dockerfile_complete,
            "api_docs": self.on_api_docs_complete,
        }

        # Add non-None callbacks to component callbacks
        for component, callback in legacy_start_mapping.items():
            if callback and component not in self.on_component_start:
                self.on_component_start[component] = callback

        for component, callback in legacy_complete_mapping.items():
            if callback and component not in self.on_component_complete:
                self.on_component_complete[component] = callback

    async def generate_code(
        self, request: CodeGenerationRequest, db: Session = Depends(get_db)
    ) -> CodeGenerationResponse:
        """
        Generate code based on the request, determining needed components for the specific language.

        Args:
            request: The code generation request containing the prompt and options

        Returns:
            A response with the generated code and metadata
        """
        try:
            # Extract request parameters
            project_id = request.project_id
            prompt = request.prompt
            language = request.language.lower() if request.language else "python"
            method = request.method or "GET"
            endpoint_path = (
                request.endpoint_path or f"/api/{prompt.lower().replace(' ', '-')}"
            )
            # Check for project existence in the database
            project = None
            project = db.query(Project).filter(Project.slug == project_id).first()
            if not project:
                logger.info(
                    f"Project with slug {project_id} not found in DB. Proceeding without DB storage."
                )
            # Initialize language template
            language_template = LanguageTemplateFactory.get_template(language)

            # --- Extract entity name from prompt before generating components ---
            # Try to derive a meaningful entity name from the prompt or endpoint path
            initial_entity_name = self._derive_entity_name(
                prompt, endpoint_path, language_template
            )
            logger.info(f"Initially derived entity name: {initial_entity_name}")

            # Start with the initial entity name
            entity_name = initial_entity_name

            # Log generation start
            logger.info(f"Generating code in {language} for: {prompt}")
            await self._notify_info(
                f"Starting code generation in {language} for: {prompt}"
            )

            # Step 1: Generate primary endpoint/controller
            primary_component = await self._generate_primary_component(
                language_template,
                project_id,
                entity_name,  # Pass the initial entity name
                prompt,
                method,
                endpoint_path,
                request.additional_context,
            )

            # Step 2: Determine if database components are needed
            needs_database = language_template.needs_database(
                primary_component.get("generated_code", "")
            )

            # Step 3: Extract entity name from generated code to confirm/refine it
            extracted_entity = language_template.extract_entity_from_code(
                primary_component.get("generated_code", "")
            )

            # If we found a valid entity name in the code and it's different from our initial guess,
            # update our entity name and adjust the component paths
            if extracted_entity and extracted_entity != entity_name:
                logger.info(f"Extracted entity name from code: {extracted_entity}")

                # Store the old entity name before updating
                old_entity_name = entity_name

                # Update to the new entity name
                entity_name = self._ensure_pascal_case(extracted_entity)
                logger.info(f"Final unified entity name: {entity_name}")

                # IMPORTANT: Update the primary component's file path to use the new entity name
                component_type = language_template.get_component_map().get("endpoint")
                new_file_path = language_template.get_component_paths(
                    project_id, entity_name, method=method, endpoint_path=endpoint_path
                )[component_type]

                # Update the primary component with the new entity name and file path
                primary_component["entity_name"] = entity_name

                # Log the file path change for debugging
                logger.info(
                    f"Updating endpoint file path from {primary_component['file_path']} to {new_file_path}"
                )
                primary_component["file_path"] = new_file_path

                # Also update the code content to replace old entity name references
                primary_component = await self._update_component_with_unified_entity(
                    primary_component, old_entity_name, entity_name, language_template
                )
            else:
                # If no entity was extracted or it matches our initial guess, ensure it's in proper format
                entity_name = self._ensure_pascal_case(entity_name)
                logger.info(f"Final unified entity name: {entity_name}")
                primary_component["entity_name"] = entity_name

            # Step 4: Initialize result dictionary with updated primary component
            component_type = language_template.get_component_map().get("endpoint")
            result = self._initialize_result_dictionary(
                primary_component,
                language_template,
                entity_name,
                needs_database,
                component_type,
            )

            # Step 5: Generate database components if needed
            if needs_database:
                await self._notify_info(f"Database components needed: {needs_database}")

                # Check for existing models
                existing_model = await self._check_for_existing_model(
                    project_id, entity_name
                )

                if existing_model:
                    # Handle model updates using ModelSchemaManager
                    await self._handle_existing_model(
                        result,
                        project_id,
                        entity_name,
                        prompt,
                        primary_component,
                        language,
                        language_template,
                    )
                else:
                    # Generate new components using the unified entity name
                    await self._generate_new_components(
                        result,
                        language_template,
                        project_id,
                        entity_name,
                        prompt,
                        primary_component,
                        method,
                        endpoint_path,
                    )

            # Step 6: Generate Dockerfile - ALWAYS generate regardless of database needs
            try:
                logger.info(f"About to generate Dockerfile for {entity_name}")
                await self._notify_event(
                    "start", "dockerfile", {"entity_name": entity_name}
                )
                dockerfile_content = await language_template.generate_dockerfile(
                    project_id, entity_name
                )
                result["dockerfile"] = {
                    "file_path": "Dockerfile",
                    "generated_code": dockerfile_content,
                    "content_base64": LangchainService.encode_content(
                        dockerfile_content
                    ),
                    "file_hash": LangchainService.generate_file_hash(
                        dockerfile_content
                    ),
                }
                await self._notify_event("complete", "dockerfile", result["dockerfile"])
                logger.info("Generated Dockerfile successfully")
            except Exception as e:
                error_msg = f"Error generating Dockerfile: {str(e)}"
                logger.error(error_msg, exc_info=True)
                await self._notify_info(error_msg)

            # Step 7: Generate API documentation - ALWAYS generate regardless of database needs
            try:
                logger.info(f"About to generate API docs for {entity_name}")
                await self._notify_event(
                    "start", "api_docs", {"entity_name": entity_name}
                )
                api_docs_content = await self._generate_api_docs(
                    project_id,
                    entity_name,  # Use the unified entity name
                    method,
                    endpoint_path,
                    result["endpoint"].get("generated_code", ""),
                )

                # Generate file path using the language template for consistency
                api_docs_path = (
                    f"docs/{language_template._to_snake_case(entity_name)}.md"
                )

                result["api_docs"] = {
                    "file_path": api_docs_path,
                    "generated_code": api_docs_content,
                    "content_base64": LangchainService.encode_content(api_docs_content),
                    "file_hash": LangchainService.generate_file_hash(api_docs_content),
                    "entity_name": entity_name,  # Include the entity name in the metadata
                }
                await self._notify_event("complete", "api_docs", result["api_docs"])
                logger.info("Generated API documentation successfully")
            except Exception as e:
                error_msg = f"Error generating API documentation: {str(e)}"
                logger.error(error_msg, exc_info=True)
                await self._notify_info(error_msg)
            # Step 8: Commit files to Git
            git_results = await self._commit_files_to_git(
                project_id, result, language, language_template
            )
            result["git_results"] = git_results

            # Step 9: Save endpoint to database if project exists
            if project:
                await self._save_endpoint_to_db(
                    db, project, result, git_results, request
                )

            # Step 10: Create and return response
            await self._notify_info("Code generation completed successfully")
            return CodeGenerationResponse(
                success=True,
                message="Code generation successful",
                result=GenerationResult(**result),
            )

        except Exception as e:
            error_msg = f"Error in code generation: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await self._notify_info(error_msg)

            return CodeGenerationResponse(success=False, message=error_msg, result=None)

    async def _generate_api_docs(
        self,
        project_id: str,
        entity_name: str,
        method: str,
        endpoint_path: str,
        endpoint_code: str,
    ) -> str:
        """
        Generate API documentation for an endpoint.
        Ensures all required template parameters are explicitly passed.

        Args:
            project_id: Project identifier
            entity_name: The entity name (singular)
            method: HTTP method
            endpoint_path: API endpoint path
            endpoint_code: Generated endpoint code

        Returns:
            str: Generated API documentation
        """
        try:
            # Create a complete set of template variables to ensure nothing is missing
            template_vars = {
                # Make sure project_id is included
                "project_id": project_id,
                "entity_name": entity_name,
                "method": method,
                "method_lower": method.lower(),
                "endpoint_path": endpoint_path,
                "endpoint_code": endpoint_code,
                # Add any other variables that might be used in the template
                "endpoint_description": f"API endpoint for {entity_name}",
                "language": "python",
            }

            # Pass all variables to the template
            result = await LangchainService.generate_code_with_template(
                template_name="api_docs", **template_vars  # Spread all variables
            )

            return result["generated_code"]
        except Exception as e:
            logger.error(f"Error generating API documentation: {str(e)}")
            # Return simple fallback documentation if generation fails
            return f"""# {entity_name} API

    ## {method.upper()} {endpoint_path}

    Basic endpoint for {entity_name} resource.

    *Documentation generation failed: {str(e)}*
    """

    async def _save_endpoint_to_db(
        self,
        db_session: Session,
        project: Project,
        result: Dict,
        git_results: Dict,
        request: CodeGenerationRequest,
    ):
        """
        Save the generated endpoint information to the database.

        Args:
            db_session: Database session
            project: Project instance
            result: Dictionary containing generation results
            git_results: Dictionary containing Git commit results
            request: Original code generation request

        Returns:
            None
        """
        try:
            if "endpoint" not in result:
                logger.warning(
                    "No endpoint information found in result, skipping DB storage"
                )
                return

            endpoint_data = result["endpoint"]
            endpoint_path = endpoint_data.get("endpoint_path") or endpoint_data.get(
                "path", ""
            )
            endpoint_method = endpoint_data.get("method", "GET")

            # Check if endpoint already exists
            existing_endpoint = (
                db_session.query(EndPoint)
                .filter(
                    EndPoint.project_id == project.id,
                    EndPoint.path == endpoint_path,
                    EndPoint.method == endpoint_method,
                )
                .first()
            )

            if not existing_endpoint:
                # Create new endpoint
                description = request.prompt
                file_hash = git_results.get("endpoint", "")

                new_endpoint = EndPoint(
                    path=endpoint_path,
                    method=endpoint_method,
                    project_id=str(project.id),
                    description=description,
                    file_hash=file_hash,
                )

                db_session.add(new_endpoint)
                db_session.commit()
                db_session.refresh(new_endpoint)
                logger.info(f"Created new endpoint in DB with ID: {new_endpoint.id}")
            else:
                logger.info(
                    f"Endpoint already exists in DB with ID: {existing_endpoint.id}"
                )

        except Exception as e:
            logger.error(f"Error saving endpoint to database: {str(e)}", exc_info=True)
            # Continue without failing the overall process

    async def _generate_primary_component(
        self,
        language_template,
        project_id: str,
        entity_name: str,  # This should be the unified entity name
        prompt: str,
        method: str,
        endpoint_path: str,
        additional_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate the primary component (usually an endpoint/controller) with a unified entity name.

        Args:
            language_template: The language template object
            project_id: Project identifier
            entity_name: The unified entity name to use for all components
            prompt: The prompt describing what to create
            method: HTTP method for the endpoint
            endpoint_path: Path for the endpoint
            additional_context: Any additional context for generation

        Returns:
            Dict[str, Any]: The generated primary component
        """
        try:
            # Log the start of primary component generation
            logger.info(f"Generating primary component for {entity_name}")
            await self._notify_event("start", "endpoint", {"entity_name": entity_name})

            # Generate the primary component with the unified entity name
            component_type = language_template.get_component_map().get("endpoint")
            primary_component = await language_template.generate_component(
                component_type=component_type,
                project_id=project_id,
                entity_name=entity_name,
                entity_description=prompt,
                method=method,
                endpoint_path=endpoint_path,
                additional_context=additional_context,
            )

            # Ensure the entity name in the component is consistent
            primary_component["entity_name"] = entity_name

            # Get the correct file path using the unified entity name
            primary_component["file_path"] = language_template.get_component_paths(
                project_id, entity_name, method=method, endpoint_path=endpoint_path
            )[component_type]

            # Log completion of primary component generation
            await self._notify_event("complete", "endpoint", primary_component)
            logger.info("Generated primary component successfully")

            return primary_component

        except Exception as e:
            error_msg = f"Error generating primary component: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await self._notify_info(error_msg)
            raise

    def _extract_entity_name(
        self, language_template, primary_component: Dict[str, Any]
    ) -> str:
        """
        Extract and standardize the entity name from the primary component.
        This improved version ensures consistent entity naming across components.

        Args:
            language_template: The language template used for extraction
            primary_component: The primary component containing the code

        Returns:
            str: The extracted and standardized entity name
        """
        extracted_entity = None

        # Try to extract from the code using language template
        if primary_component and "generated_code" in primary_component:
            extracted_entity = language_template.extract_entity_from_code(
                primary_component["generated_code"]
            )

        # If we have an entity name from the component metadata, use it as backup
        if not extracted_entity and "entity_name" in primary_component:
            extracted_entity = primary_component["entity_name"]

        # If we still don't have an entity name, use a default
        if not extracted_entity:
            extracted_entity = "Resource"

        # Standardize the entity name to PascalCase
        return self._ensure_pascal_case(extracted_entity)

    def _initialize_result_dictionary(
        self,
        primary_component,
        language_template,
        entity_name,
        needs_database,
        component_type,
    ):
        """
        Initialize the result dictionary with common fields and primary component data.

        This method creates the base structure for the generation result that will be
        populated with all generated components and metadata throughout the generation process.

        Args:
            primary_component: Dictionary containing the generated primary component
            language_template: Template for the target programming language
            entity_name: Name of the main entity being operated on
            needs_database: Boolean indicating if database components are required
            component_type: Type of the primary component (endpoint, controller, etc.)

        Returns:
            Dict: Initialized result dictionary with primary component and metadata
        """
        return {
            component_type: primary_component,
            "language": language_template.get_file_extension(),
            "file_extension": language_template.get_file_extension(),
            "entity_name": entity_name,
            "detected_database_usage": needs_database,
        }

    async def _handle_existing_model(
        self,
        result,
        project_id,
        entity_name,
        prompt,
        primary_component,
        language,
        language_template,
    ):
        """
        Handle updates to an existing model when generating code for an entity that already exists.

        This method uses ModelSchemaManager to check for an existing model and updates it if needed
        based on the new endpoint's requirements.

        Args:
            result: Dictionary to store generation results
            project_id: Identifier for the project being modified
            entity_name: Name of the entity being updated
            prompt: Natural language description of the desired functionality
            primary_component: Dictionary containing the generated primary component
            language: Target programming language
            language_template: Template for the target programming language

        Returns:
            None: Results are added directly to the result dictionary
        """
        await self._notify_info(
            f"Found existing model for {entity_name}, checking for updates..."
        )

        # Process potential model updates using ModelSchemaManager
        update_result = await ModelSchemaManager.process_model_changes(
            project_id=project_id,
            entity_name=entity_name,
            prompt_description=prompt,
            endpoint_code=primary_component.get("generated_code", ""),
            generate_migration=True,  # Generate migration if needed
            language=language,
        )

        if update_result and update_result.get("model_updated", False):
            # Model was updated
            await self._notify_info(f"Updated existing model {entity_name}")

            # Extract the raw content from base64
            raw_model_content = ""
            if update_result.get("content_base64"):
                try:
                    import base64

                    raw_model_content = base64.b64decode(
                        update_result.get("content_base64")
                    ).decode("utf-8")
                except Exception as e:
                    logger.error(f"Error decoding model content: {str(e)}")

                    # Fallback: try to get content from files_to_commit
                    if update_result.get("files_to_commit"):
                        model_file_path = update_result.get("model_file")
                        for file_info in update_result.get("files_to_commit", []):
                            if file_info.get("file_path") == model_file_path:
                                raw_model_content = file_info.get("content", "")
                                break

            # Add model update details
            result["model"] = {
                "exists": True,
                "updated": True,
                "entity_name": entity_name,
                "file_path": update_result.get("model_file"),
                "generated_code": raw_model_content,
                "content_base64": update_result.get("content_base64"),
                "file_hash": update_result.get("file_hash"),
                "update_details": update_result.get("field_changes"),
            }

            # Add schema update results if applicable
            if update_result.get("schema_updated", False):
                # Get the schema code from the update result
                schema_code = update_result.get("schema_code")
                # Check if schema_code is None and provide a default if needed
                if schema_code is None:
                    # Try to get schema content from schema_results
                    for schema_result in update_result.get("schema_results", []):
                        if schema_result.get("content"):
                            schema_code = schema_result.get("content")
                            break

                    # If still None, use a placeholder
                    if schema_code is None:
                        schema_code = f"# Schema for {entity_name}"
                schema_results = update_result.get("schema_results", [])
                result["schema"] = {
                    "file_path": update_result.get(
                        "schema_file",
                        f"schemas/{entity_name.lower()}{LangchainService.get_file_extension(language)}",
                    ),
                    "generated_code": schema_code,
                    "content_base64": update_result.get(
                        "schema_content_base64",
                        LangchainService.encode_content(schema_code),
                    ),
                    "file_hash": update_result.get(
                        "schema_file_hash",
                        LangchainService.generate_file_hash(schema_code),
                    ),
                    "exists": True,
                    "updated": True,
                    "entity_name": entity_name,
                    "schema_details": schema_results,
                }

            # Add migration if it was generated during the update
            if update_result.get("migration"):
                result["migration"] = update_result.get("migration")

                if (
                    "file_hash" not in result["migration"]
                    and "generated_code" in result["migration"]
                ):
                    result["migration"]["file_hash"] = (
                        LangchainService.generate_file_hash(
                            result["migration"]["generated_code"]
                        )
                    )
                if (
                    "content_base64" not in result["migration"]
                    and "generated_code" in result["migration"]
                ):
                    result["migration"]["content_base64"] = (
                        LangchainService.encode_content(
                            result["migration"]["generated_code"]
                        )
                    )

            # Add files to commit from the update
            if update_result.get("files_to_commit"):
                if "files_to_commit" not in result:
                    result["files_to_commit"] = []
                result["files_to_commit"].extend(update_result.get("files_to_commit"))
        else:
            await self._notify_info(
                f"No updates needed for existing model {entity_name}"
            )

    async def _update_component_with_unified_entity(
        self,
        component: Dict[str, Any],
        old_entity_name: str,
        new_entity_name: str,
        language_template,
    ) -> Dict[str, Any]:
        """
        Updates a component's code with the unified entity name.

        Args:
            component: The component dictionary containing the generated code
            old_entity_name: The original entity name to replace
            new_entity_name: The new unified entity name
            language_template: The language template for generating paths

        Returns:
            Dict: The updated component
        """
        if not component or not component.get("generated_code"):
            return component

        code = component["generated_code"]

        # Create regex patterns for different case formats
        snake_old = language_template._to_snake_case(old_entity_name)
        snake_new = language_template._to_snake_case(new_entity_name)

        camel_old = (
            old_entity_name[0].lower() + old_entity_name[1:] if old_entity_name else ""
        )
        camel_new = (
            new_entity_name[0].lower() + new_entity_name[1:] if new_entity_name else ""
        )

        # Create a dictionary of replacements
        replacements = {
            # PascalCase
            old_entity_name: new_entity_name,
            # snake_case
            snake_old: snake_new,
            # camelCase
            camel_old: camel_new,
            # Plurals for common words (collections, tables, etc.)
            f"{snake_old}s": f"{snake_new}s",
            f"{old_entity_name}s": f"{new_entity_name}s",
        }

        # Apply all replacements
        for old, new in replacements.items():
            if old and old != new:  # Only replace if different and not empty
                code = code.replace(old, new)

        # Update the code in the component
        component["generated_code"] = code

        # Update entity_name in the component metadata
        if "entity_name" in component:
            component["entity_name"] = new_entity_name

        # Update file paths if they contain the entity name
        if "file_path" in component:
            # Keep the same component type but update the entity name part of the path
            component_file = component["file_path"]

            # Generate new path based on the new entity name but preserve the same component type
            for component_type, path in language_template.get_component_map().items():
                if path and path in component_file:
                    new_paths = language_template.get_component_paths(
                        project_id="", entity_name=new_entity_name
                    )
                    component["file_path"] = new_paths[component_type]
                    break

        return component

    async def _generate_new_components(
        self,
        result: Dict[str, Any],
        language_template,
        project_id: str,
        entity_name: str,
        prompt: str,
        primary_component: Dict[str, Any],
        method: str,
        endpoint_path: str,
    ) -> None:
        """
        Generate all new components for an entity using the unified entity name.
        This method creates all necessary components for a new entity based on the
        language template's requirements.

        Args:
            result: Dictionary to store generation results
            language_template: Template for the target programming language
            project_id: Identifier for the project being modified
            entity_name: Name of the entity to create (unified)
            prompt: Natural language description of the desired functionality
            primary_component: Dictionary containing the generated primary component
            method: HTTP method for the endpoint (GET, POST, etc.)
            endpoint_path: URL path for the endpoint
        """
        await self._notify_info(f"Generating new components for {entity_name}")

        # Get component information from language template
        component_map = language_template.get_component_map()
        required_components = language_template.get_required_components()

        # Get endpoint component type
        endpoint_component = component_map.get("endpoint")
        if endpoint_component is None:
            raise ValueError(
                "Language template does not define an 'endpoint' component."
            )

        # Keep track of generated code for dependencies
        generated_code = {
            "endpoint_code": primary_component.get("generated_code", ""),
            "controller_code": primary_component.get("generated_code", ""),
            "model_code": None,
        }

        # Generate each required component except migrations (handled separately)
        for component_type in required_components:
            # Skip the primary component as we've already generated it
            if component_type == endpoint_component or component_type == "migration":
                continue

            try:
                # Notify start of component generation
                await self._notify_event(
                    "start", component_type, {"entity_name": entity_name}
                )
                logger.info(f"Generating {component_type} for {entity_name}")

                # Generate the component with the unified entity name
                component = await language_template.generate_component(
                    component_type=component_type,
                    project_id=project_id,
                    entity_name=entity_name,
                    entity_description=prompt,
                    endpoint_code=generated_code.get("endpoint_code", ""),
                    controller_code=generated_code.get("controller_code", ""),
                    model_code=generated_code.get("model_code", ""),
                    method=method,
                    endpoint_path=endpoint_path,
                )

                # Add to result
                result[component_type] = component

                # Store generated code for dependencies
                if component_type == component_map.get("model"):
                    generated_code["model_code"] = component.get("generated_code", "")

                # Notify completion of component generation
                await self._notify_event("complete", component_type, component)
                logger.info(f"Generated {component_type} successfully")

            except Exception as e:
                error_msg = f"Error generating {component_type}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                await self._notify_info(error_msg)

        # Now handle migrations separately using the appropriate method for the language
        if "migration" in required_components:
            await self._generate_migration(
                project_id, entity_name, result, language_template
            )

    async def _generate_component(
        self,
        language_template,
        component_type,
        project_id,
        entity_name,
        entity_description,
        **kwargs,
    ):
        """
        Generate a specific component using the language template and notify progress.

        This method handles the generation of an individual component (e.g., model, schema)
        using the language-specific template and triggers appropriate events to notify
        progress to listeners.

        Args:
            language_template: Template for the target programming language
            component_type: Type of component to generate (model, schema, etc.)
            project_id: Identifier for the project being modified
            entity_name: Name of the entity the component is for
            entity_description: Natural language description of the entity
            **kwargs: Additional parameters for component generation (varies by component type)

        Returns:
            Dict: Component data including generated code, file path, and metadata

        Raises:
            Exception: Any errors during component generation are logged and re-raised
        """
        try:
            # Notify component generation start
            await self._notify_event(
                "start",
                component_type,
                {"entity_name": entity_name, "component_type": component_type},
            )

            # Generate the component
            result = await language_template.generate_component(
                component_type=component_type,
                project_id=project_id,
                entity_name=entity_name,
                entity_description=entity_description,
                **kwargs,
            )

            # Notify component generation complete
            await self._notify_event("complete", component_type, result)

            return result
        except Exception as e:
            logger.error(f"Error generating {component_type}: {str(e)}", exc_info=True)
            raise

    async def _generate_migration(
        self, project_id: str, entity_name: str, result: dict, language_template
    ):
        """
        Generates migration files without applying them to the database.
        This function delegates the migration generation to the language_template.generate_migration method,
        and takes care of tracking the resulting files for Git commits.

        Args:
            project_id (str): The unique identifier of the project.
            entity_name (str): The name of the entity/model for which migrations are to be generated.
            result (dict): A dictionary to store generated migration components and files to commit.
            language_template: An object providing language-specific migration generation methods.
        Returns:
            The updated result dictionary with migration files and information.
        """
        from app.api.v1.utils.endpoint_services import get_project_dir_from_repo_url
        from app.api.v1.utils.git_utils import get_repo_url

        repo_url = get_repo_url(project_id)
        project_dir = get_project_dir_from_repo_url(repo_url)

        try:
            # Notify that migration generation is starting
            migration_data = {"entity_name": entity_name, "component_type": "migration"}
            await self._notify_event("start", "migration", migration_data)
            await self._notify_info(f"Starting migration generation for {entity_name}")

            # Generate migrations using the language template's generate_migration method
            migration_result = await language_template.generate_migration(
                project_dir=project_dir, entity_name=entity_name
            )

            # Add the generated migration files to the result for tracking
            if migration_result and isinstance(migration_result, dict):
                # The template might return information we can use directly
                if "migration_files" in migration_result:
                    for file_info in migration_result["migration_files"]:
                        result.setdefault("files_to_commit", []).append(file_info)

                # If the template returned migration component information
                if (
                    "migration_component" in migration_result
                    and migration_result["migration_component"]
                ):
                    result["migration"] = migration_result["migration_component"]

                    # Ensure we have all required fields in the migration component
                    if "entity_name" not in result["migration"]:
                        result["migration"]["entity_name"] = entity_name
                else:
                    # If no structured component was returned, we need to find migration files ourselves
                    versions_dir = project_dir / "alembic" / "versions"
                    if versions_dir.exists():
                        await self._add_migration_files_to_results(
                            project_dir, versions_dir, result
                        )

                        # If we found migration files but still don't have a migration component, create one
                        if "migration" not in result and "files_to_commit" in result:
                            for file_info in result["files_to_commit"]:
                                if file_info.get("file_path", "").startswith(
                                    "alembic/versions/"
                                ):
                                    result["migration"] = {
                                        "file_path": file_info["file_path"],
                                        "generated_code": file_info.get(
                                            "generated_code", ""
                                        ),
                                        "content_base64": file_info.get(
                                            "content_base64", ""
                                        ),
                                        "file_hash": file_info.get("file_hash", ""),
                                        "entity_name": entity_name,
                                    }
                                    break
            else:
                # If no structured result was returned, we need to find migration files ourselves
                versions_dir = project_dir / "alembic" / "versions"
                if versions_dir.exists():
                    await self._add_migration_files_to_results(
                        project_dir, versions_dir, result
                    )

            # Check for the database directory and ensure it exists
            storage_dir = project_dir / "storage" / "db"
            storage_dir.mkdir(exist_ok=True, parents=True)

            # Create a .gitkeep file to ensure Git tracks the directory
            gitkeep_path = storage_dir / ".gitkeep"
            try:
                with open(gitkeep_path, "w") as f:
                    f.write(
                        "# This file ensures Git tracks this directory even when empty"
                    )

                # Add .gitkeep to files_to_commit
                result.setdefault("files_to_commit", []).append(
                    {
                        "file_path": str(gitkeep_path.relative_to(project_dir)),
                        "generated_code": "# This file ensures Git tracks this directory even when empty",
                        "content_base64": LangchainService.encode_content(
                            "# This file ensures Git tracks this directory even when empty"
                        ),
                        "file_hash": LangchainService.generate_file_hash(
                            "# This file ensures Git tracks this directory even when empty"
                        ),
                    }
                )
            except Exception as e:
                logger.error(f"Error creating .gitkeep file: {str(e)}")
                await self._notify_info(f"Failed to create .gitkeep file: {str(e)}")

            # Notify that migration generation is complete
            migration_data = result.get(
                "migration", {"entity_name": entity_name, "component_type": "migration"}
            )
            await self._notify_event("complete", "migration", migration_data)

        except Exception as e:
            error_msg = f"Error in migration generation: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await self._notify_info(error_msg)

        return result

    async def _add_migration_files_to_results(
        self, project_dir: Path, versions_dir: Path, result: dict
    ):
        """Helper method to add migration files to the results for Git commits"""
        for migration_file in versions_dir.glob("*.py"):
            if str(migration_file).endswith("__pycache__"):
                continue

            try:
                file_path = str(migration_file.relative_to(project_dir))
                migration_content = migration_file.read_text(encoding="utf-8")

                # Check if we already have this file in the result
                if (
                    "migration" in result
                    and result["migration"].get("file_path") == file_path
                ):
                    continue

                # Add file to commit list
                result.setdefault("files_to_commit", []).append(
                    {
                        "file_path": file_path,
                        "generated_code": migration_content,
                        "content_base64": LangchainService.encode_content(
                            migration_content
                        ),
                        "file_hash": LangchainService.generate_file_hash(
                            migration_content
                        ),
                    }
                )
            except Exception as file_error:
                logger.error(
                    f"Error reading migration file {migration_file}: {str(file_error)}"
                )

    async def _add_db_to_results(
        self, project_dir: Path, sqlite_path: Path, result: dict, entity_name: str
    ):
        """Helper method to add the database file to results for Git commits"""
        try:
            sqlite_db_path = str(sqlite_path.relative_to(project_dir))

            # Read the database file
            with open(sqlite_path, "rb") as f:
                sqlite_data = f.read()

            # Add a explicit database component to the result
            result["database"] = {
                "file_path": sqlite_db_path,
                "is_binary": True,
                "generated_code": sqlite_data,
                "content_base64": base64.b64encode(sqlite_data).decode("utf-8"),
                "file_hash": hashlib.md5(sqlite_data).hexdigest(),
            }

            # Also add to files_to_commit for consistency
            result.setdefault("files_to_commit", []).append(
                {
                    "file_path": sqlite_db_path,
                    "is_binary": True,
                    "generated_code": sqlite_data,
                    "content_base64": base64.b64encode(sqlite_data).decode("utf-8"),
                    "file_hash": hashlib.md5(sqlite_data).hexdigest(),
                }
            )

            await self._notify_info("Added SQLite database file to result")
        except Exception as db_error:
            logger.error(f"Error including SQLite database in result: {str(db_error)}")

    async def _check_for_existing_model(self, project_id, entity_name):
        """
        Check if an entity model already exists in the project.

        This method analyzes the project structure to find existing model definitions
        that match the requested entity name, using fuzzy matching to handle variations
        in naming conventions.

        Args:
            project_id: Identifier for the project being checked
            entity_name: Name of the entity to look for

        Returns:
            Dict or None: Existing model data if found, None otherwise

        Raises:
            Exception: Errors during project analysis are caught and logged
        """
        try:
            # Analyze project to find existing models
            project_analysis = await ProjectAnalysisService.analyze_project(project_id)

            # Find matching model
            return LLMService._find_existing_model(
                entity_name, project_analysis.get("models", [])
            )
        except Exception as e:
            logger.error(f"Error checking for existing model: {str(e)}", exc_info=True)
            return None

    async def _commit_files_to_git(
        self, project_id, generation_result, language, language_template
    ):
        """
        Commit all generated files to Git repository.

        This method handles committing all components to Git with appropriate commit messages,
        ensuring each file is only committed once.

        Args:
            project_id: Identifier for the project repository
            generation_result: Dictionary containing all generated components
            language: Target programming language
            language_template: Template for the target programming language

        Returns:
            Dict: Results of commit operations by component type
        """
        git_results = {}
        entity_name = generation_result.get("entity_name", "Entity")

        # Determine commit order and messages
        try:
            # Try to get language-specific commit strategy
            commit_strategy = language_template.get_commit_strategy()
            commit_order = commit_strategy.get("commit_order", [])
            commit_messages = commit_strategy.get("commit_messages", {})
        except Exception:
            # Fallback to default order if strategy retrieval fails
            commit_order = [
                "model",
                "schema",
                "migration",
                "endpoint",
                "controller",
                "helpers",
                "utils",
                "route",
                "validation",
                "dockerfile",
                "api_docs",
                "database",
            ]
            commit_messages = {}

        # Add/override commit messages for Dockerfile and API docs
        commit_messages.update(
            {
                "dockerfile": f"Add Dockerfile for {entity_name}",
                "api_docs": f"Add API documentation for {entity_name}",
                "database": f"Add SQLite database for {entity_name}",
            }
        )

        # Log the available components before processing
        logger.info(
            f"Components available in generation_result: {list(generation_result.keys())}"
        )

        # Check for files_to_commit, which might contain the database file
        if "files_to_commit" in generation_result:
            files_to_commit = generation_result.get("files_to_commit", [])
            logger.info(f"Found {len(files_to_commit)} additional files to commit")

            # Process files_to_commit first - especially for database files
            for file_info in files_to_commit:
                file_path = file_info.get("file_path")
                if not file_path:
                    continue

                # Check if this is a database file
                is_database = "storage/db/db.sqlite" in file_path
                is_binary = file_info.get("is_binary", False)

                if is_database:
                    logger.info(f"Processing database file: {file_path}")
                    try:
                        commit_message = commit_messages.get(
                            "database", f"Add SQLite database for {entity_name}"
                        )

                        # For binary files, use the binary commit method
                        if is_binary:
                            # Get the binary content
                            binary_content = file_info.get("generated_code")
                            if not isinstance(binary_content, bytes):
                                # If it's not already bytes, try to convert it
                                if isinstance(binary_content, str):
                                    # It might be base64 encoded
                                    import base64

                                    try:
                                        binary_content = base64.b64decode(
                                            binary_content
                                        )
                                    except Exception as e:
                                        logger.debug(
                                            f"Failed to decode as base64: {str(e)}. Encoding as UTF-8 instead."
                                        )
                                        binary_content = binary_content.encode("utf-8")

                            # Use the binary commit method
                            commit_result = await GitService.commit_binary_file_update(
                                project_id=project_id,
                                binary_content=binary_content,
                                file_path=file_path,
                                commit_message=commit_message,
                            )
                        else:
                            # Regular file commit
                            commit_result = await GitService.commit_file_update(
                                project_id=project_id,
                                new_code=file_info.get("generated_code", ""),
                                file_path=file_path,
                                commit_message=commit_message,
                            )

                        # Store the result
                        git_results["database"] = commit_result
                        logger.info(f"Committed database file: {file_path}")

                        # Mark as committed to avoid duplicate commits
                        file_info["already_committed"] = True

                    except Exception as e:
                        logger.error(
                            f"Failed to commit database file: {str(e)}", exc_info=True
                        )

        # Check specifically if dockerfile and api_docs are in the result
        logger.info(f"Dockerfile in result: {'dockerfile' in generation_result}")
        logger.info(f"API docs in result: {'api_docs' in generation_result}")

        if "dockerfile" in generation_result:
            logger.info(
                f"Dockerfile file_path: {generation_result['dockerfile'].get('file_path')}"
            )
            logger.info(
                f"Dockerfile has code: {bool(generation_result['dockerfile'].get('generated_code'))}"
            )

        if "api_docs" in generation_result:
            logger.info(
                f"API docs file_path: {generation_result['api_docs'].get('file_path')}"
            )
            logger.info(
                f"API docs has code: {bool(generation_result['api_docs'].get('generated_code'))}"
            )

        # Process each component type in order
        for component_type in commit_order:
            logger.info(f"Processing component type: {component_type}")

            # Add special logging for dockerfile and api_docs
            if component_type == "dockerfile":
                logger.info(
                    f"Processing Dockerfile commit, exists in result: {'dockerfile' in generation_result}"
                )

            if component_type == "api_docs":
                logger.info(
                    f"Processing API docs commit, exists in result: {'api_docs' in generation_result}"
                )

            # Handle component aliases (e.g., controller/endpoint, validation/schema)
            if component_type == "controller":
                component_data = generation_result.get(
                    "controller"
                ) or generation_result.get("endpoint", {})
            elif component_type == "validation":
                component_data = generation_result.get(
                    "validation"
                ) or generation_result.get("schema", {})
            elif component_type == "utils":
                component_data = generation_result.get(
                    "utils"
                ) or generation_result.get("helpers", {})
            else:
                component_data = generation_result.get(component_type, {})

            # Skip if component doesn't exist or was already committed
            if not component_data or component_data.get("already_committed", False):
                logger.info(
                    f"Skipping {component_type} - not found or already committed"
                )
                continue

            # Skip if no generated code or file path
            if not component_data.get("generated_code") or not component_data.get(
                "file_path"
            ):
                logger.info(
                    f"Skipping {component_type} - no generated code or file path"
                )
                continue

            # Skip if component exists but wasn't actually updated (except endpoints which should always be committed)
            if (
                component_data.get("exists", False)
                and not component_data.get("updated", False)
                and component_type not in ["endpoint", "controller"]
            ):
                logger.info(
                    f"Skipping commit for {component_type} as it exists but wasn't updated: {component_data.get('file_path')}"
                )
                continue

            try:
                # Determine appropriate commit message
                if component_type in commit_messages:
                    # Use language template's message format
                    message_template = commit_messages[component_type]
                    commit_message = message_template.format(
                        entity_name=entity_name,
                        method=component_data.get("method", "GET"),
                        endpoint_path=component_data.get("endpoint_path", ""),
                    )
                else:
                    # Use default message format based on component type
                    if component_type in ["endpoint", "controller"]:
                        commit_message = f"Add {component_data.get('method', 'GET')} endpoint for {component_data.get('endpoint_path', '')}"
                    elif component_type == "migration":
                        commit_message = f"Add migration for {entity_name} model"
                    else:
                        # Generic message for other component types
                        component_name = component_type.replace("_", " ")
                        commit_message = f"Add {entity_name} {component_name}"

                    # Add "Update" instead of "Add" for existing components
                    if component_data.get("exists", False) and component_data.get(
                        "updated", False
                    ):
                        commit_message = commit_message.replace("Add", "Update")

                logger.info(
                    f"Committing {component_type} with message: {commit_message}"
                )

                # Commit the file
                commit_result = await GitService.commit_file_update(
                    project_id=project_id,
                    new_code=component_data.get("generated_code", ""),
                    file_path=component_data.get("file_path", ""),
                    commit_message=commit_message,
                )

                # Store the result
                git_results[component_type] = commit_result

                # Mark as committed to avoid duplicate commits
                component_data["already_committed"] = True

                logger.info(
                    f"Committed {component_type} file: {component_data.get('file_path')}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to commit {component_type}: {str(e)}", exc_info=True
                )

        # After the regular component processing loop, explicitly handle dockerfile and api_docs
        for special_component in ["dockerfile", "api_docs"]:
            logger.info(f"Explicitly processing {special_component}")

            component_data = generation_result.get(special_component, {})

            # Skip if component doesn't exist or was already committed
            if not component_data or component_data.get("already_committed", False):
                logger.info(
                    f"Skipping explicit {special_component} - not found or already committed"
                )
                continue

            # Skip if no generated code or file path
            if not component_data.get("generated_code") or not component_data.get(
                "file_path"
            ):
                logger.info(
                    f"Skipping explicit {special_component} - no generated code or file path"
                )
                continue

            try:
                # Use default message
                commit_message = (
                    f"Add {entity_name} {special_component.replace('_', ' ')}"
                )

                logger.info(
                    f"Explicitly committing {special_component} with message: {commit_message}"
                )

                # Commit the file
                commit_result = await GitService.commit_file_update(
                    project_id=project_id,
                    new_code=component_data.get("generated_code", ""),
                    file_path=component_data.get("file_path", ""),
                    commit_message=commit_message,
                )

                # Store the result
                git_results[special_component] = commit_result

                # Mark as committed
                component_data["already_committed"] = True

                logger.info(
                    f"Explicitly committed {special_component} file: {component_data.get('file_path')}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to explicitly commit {special_component}: {str(e)}",
                    exc_info=True,
                )

        return git_results

    async def _notify_event(self, event_type, component_type, data):
        """
        Notify event callbacks for a component generation event.

        This method dispatches event notifications to registered callbacks when
        component generation starts or completes. It attempts to call component-specific
        callbacks first, then falls back to generic callbacks if available.

        Args:
            event_type (str): Type of event ("start" or "complete")
            component_type (str): Type of component the event is for
            data (Dict): Event data to pass to callbacks

        Returns:
            None
        """
        callback_dict = (
            self.on_component_start
            if event_type == "start"
            else self.on_component_complete
        )

        # Try specific component callback
        callback = callback_dict.get(component_type)
        if callback:
            try:
                await callback(component_type, data)
            except Exception as e:
                logger.error(
                    f"Error in {event_type} callback for {component_type}: {str(e)}"
                )

        # Try generic callback
        generic_callback = callback_dict.get("*")
        if generic_callback:
            try:
                await generic_callback(component_type, data)
            except Exception as e:
                logger.error(f"Error in generic {event_type} callback: {str(e)}")

    async def _notify_info(self, message):
        """
        Send an informational message through the registered info callback.

        This method sends status updates and progress information to the registered
        info callback if one is available. These messages are useful for logging and
        user interface updates during the code generation process.

        Args:
            message (str): Information message to send

        Returns:
            None
        """
        if self.on_info:
            try:
                await self.on_info(message)
            except Exception as e:
                logger.error(f"Error in info callback: {str(e)}")

    def _derive_entity_name(
        self, prompt: str, endpoint_path: str, language_template
    ) -> str:
        """
        Derive a meaningful entity name from either the prompt or endpoint path.
        This is used to establish a consistent entity name early in the process.

        Args:
            prompt: The user's prompt describing what to create
            endpoint_path: The API endpoint path
            language_template: The language template object that has entity extraction methods

        Returns:
            str: A derived entity name in proper format (e.g., PascalCase)
        """
        # First try to extract from the prompt using language template's method
        entity_from_prompt = language_template.extract_entity_from_prompt(prompt)
        if entity_from_prompt:
            return entity_from_prompt

        # If that fails, try extracting from the endpoint path
        if endpoint_path:
            # Extract the last segment of the path
            path_segments = endpoint_path.strip("/").split("/")
            last_segment = path_segments[-1] if path_segments else ""

            if last_segment:
                # Convert to singular if plural
                if last_segment.endswith("s") and not last_segment.endswith("ss"):
                    last_segment = last_segment[:-1]

                # Convert to PascalCase
                return self._ensure_pascal_case(last_segment)

        # Default fallback
        return "Resource"

    def _ensure_pascal_case(self, name: str) -> str:
        """
        Ensure the entity name is in PascalCase format.

        Args:
            name: The entity name to format

        Returns:
            str: The entity name in PascalCase
        """
        if not name:
            return "Resource"

        # Remove non-alphanumeric characters
        name = "".join(c for c in name if c.isalnum() or c == "_")

        # Handle snake_case or kebab-case conversion
        if "_" in name or "-" in name:
            parts = name.replace("-", "_").split("_")
            name = "".join(p.capitalize() for p in parts if p)

        # Handle camelCase
        elif name and name[0].islower() and any(c.isupper() for c in name):
            name = name[0].upper() + name[1:]

        # Handle all lowercase
        elif name.islower():
            name = name.capitalize()

        # Handle plural to singular for common patterns
        if name.endswith("ies"):
            name = name[:-3] + "y"
        elif name.endswith("s") and len(name) > 2 and not name.endswith("ss"):
            name = name[:-1]

        # Ensure the first character is uppercase
        if name and name[0].islower():
            name = name[0].upper() + name[1:]

        return name
