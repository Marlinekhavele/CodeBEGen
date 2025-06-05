import logging
import os
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

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
from app.api.v1.services.code_quality_service import CodeQualityService
from app.api.v1.services.enhanced_quality_middleware import (
    EnhancedCodeGenerationQualityMiddleware,
)
from app.api.v1.services.langchain_service import LangchainService
from app.api.v1.services.language_templates import LanguageTemplateFactory
from app.api.v1.services.model_schema_update.model_schema_manager import (
    ModelSchemaManager,
)
from app.api.v1.services.quality_config_manager import (
    QualityConfigLevel,
    QualityConfigManager,
)
from app.api.v1.services.quality_metrics_collector import QualityMetricsCollector
from app.api.v1.services.quality_pipeline_orchestrator import (
    QualityAssurancePipeline,
    QualityLevel,
)

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
        self.on_migration_complete = (
            on_migration_complete  # Store new Dockerfile and API docs callbacks
        )
        self.on_dockerfile_start = on_dockerfile_start
        self.on_dockerfile_complete = on_dockerfile_complete
        self.on_api_docs_start = on_api_docs_start
        self.on_api_docs_complete = (
            on_api_docs_complete  # Initialize enhanced quality pipeline and components
        )
        self.quality_config_manager = QualityConfigManager()
        self.quality_metrics_collector = QualityMetricsCollector()
        self.enhanced_quality_middleware = EnhancedCodeGenerationQualityMiddleware()

        # Legacy quality components (for backward compatibility)
        self.code_quality_service = CodeQualityService()
        self.quality_pipeline = QualityAssurancePipeline()

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
            )  # Check for project existence in the database
            project = None
            if db is not None:
                project = db.query(Project).filter(Project.slug == project_id).first()
            if not project:
                logger.info(
                    f"Project with slug {project_id} not found in DB. Proceeding without DB storage."
                )  # Initialize language template
            language_template = LanguageTemplateFactory.get_template(language)

            # Set project directory for Git operations
            try:
                from app.api.v1.utils.endpoint_services import (
                    get_project_dir_from_repo_url,
                )
                from app.api.v1.utils.git_utils import get_repo_url

                repo_url = get_repo_url(project_id)
                project_directory = get_project_dir_from_repo_url(repo_url)
                language_template.project_directory = str(project_directory)
                logger.info(
                    f"Set project directory for Git operations: {project_directory}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to set project directory for Git operations: {str(e)}"
                )
                language_template.project_directory = None

            # --- Extract entity name from prompt before generating components ---
            # Try to derive a meaningful entity name from the prompt or endpoint path
            initial_entity_name = self._derive_entity_name(
                prompt, endpoint_path, language_template
            )
            logger.info(f"Initially derived entity name: {initial_entity_name}")

            # Start with the initial entity name
            entity_name = initial_entity_name  # Log generation start
            logger.info(f"Generating code in {language} for: {prompt}")
            await self._notify_info(
                f"Starting code generation in {language} for: {prompt}"
            )  # TIER 1: Prompt Enhancement (Prevention-First Quality Strategy)
            enhanced_prompt = await self._apply_tier1_prompt_enhancement(
                prompt, language, project_id, request.additional_context
            )
            logger.info("Enhanced prompt applied for quality improvement")

            # Step 1: Generate primary endpoint/controller
            primary_component = await self._generate_primary_component(
                language_template,
                project_id,
                entity_name,
                enhanced_prompt,  # Use enhanced prompt
                method,
                endpoint_path,
                request.additional_context,
            )

            # Step 2: Extract entity name from generated code to confirm/refine it
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
                primary_component["file_path"] = (
                    new_file_path  # Also update the code content to replace old entity name references
                )
                primary_component = await self._update_component_with_unified_entity(
                    primary_component, old_entity_name, entity_name, language_template
                )
            else:
                # If no entity was extracted or it matches our initial guess, ensure it's in proper format
                entity_name = self._ensure_pascal_case(entity_name)
                logger.info(f"Final unified entity name: {entity_name}")
                primary_component["entity_name"] = entity_name

            # Step 3: Determine if database components are needed
            needs_database = language_template.needs_database(
                primary_component.get("generated_code", "")
            )  # Step 4: Initialize result dictionary with updated primary component
            component_type = language_template.get_component_map().get("endpoint")
            result = self._initialize_result_dictionary(
                primary_component,
                language_template,
                entity_name,
                needs_database,
                component_type,
            )  # Step 4.5: Apply Tier 2 & 3 Quality Processing (Real-time + Auto-fixing)
            if primary_component and "generated_code" in primary_component:
                primary_component = await self._apply_tier2_tier3_quality_processing(
                    primary_component, language, project_id, entity_name
                )
                logger.info(
                    "Applied Tier 2 & 3 quality processing to primary component"
                )

            # Write the primary endpoint component to disk
            if (
                primary_component
                and "file_path" in primary_component
                and "generated_code" in primary_component
            ):
                endpoint_file_path = primary_component["file_path"]
                endpoint_code = primary_component["generated_code"]

                # Normalize to relative path
                rel_path = endpoint_file_path
                if rel_path.replace("\\", "/").startswith(f"repos/{project_id}/"):
                    rel_path = rel_path[len(f"repos/{project_id}/") :].lstrip("/\\")
                    primary_component["file_path"] = rel_path

                # Write the primary endpoint to disk
                logger.info(f"Writing primary endpoint to disk: {rel_path}")
                self._write_generated_file(project_id, rel_path, endpoint_code)

                # Initialize files_to_commit if not present
                if "files_to_commit" not in result:
                    result["files_to_commit"] = []

                # Add primary endpoint to files_to_commit
                result["files_to_commit"].append(
                    {
                        "file_path": rel_path,
                        "generated_code": endpoint_code,
                        "content_base64": primary_component.get("content_base64"),
                        "file_hash": primary_component.get("file_hash"),
                    }
                )

                logger.info(
                    f"Successfully wrote primary endpoint component to {rel_path}"
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
                else:  # Generate new components using the unified entity name
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
            else:
                # Still generate non-database components (schema and helpers if needed)
                await self._generate_new_components(
                    result,
                    language_template,
                    project_id,
                    entity_name,
                    prompt,
                    primary_component,
                    method,
                    endpoint_path,
                )  # Step 5.5: Write all generated components to disk
            await self._write_all_components_to_disk(
                result, project_id, language, entity_name
            )

            # Step 6: Generate API documentation with schema and model information
            try:
                logger.info(
                    f"About to generate comprehensive API docs for {entity_name}"
                )
                await self._notify_event(
                    "start", "api_docs", {"entity_name": entity_name}
                )

                # Extract schema and model code from generated components
                schema_code = None
                model_code = None

                if "schema" in result and result["schema"]:
                    schema_code = result["schema"].get("generated_code")

                if "model" in result and result["model"]:
                    model_code = result["model"].get("generated_code")

                api_docs_content = await self._generate_api_docs(
                    project_id,
                    entity_name,
                    method,
                    endpoint_path,
                    primary_component.get("generated_code", ""),
                    schema_code=schema_code,
                    model_code=model_code,
                )

                # Get the API documentation path from the same function that generates the endpoint path
                # This ensures they use the same naming convention
                component_paths = language_template.get_component_paths(
                    project_id, entity_name, method=method, endpoint_path=endpoint_path
                )
                api_docs_path = component_paths["api_docs"]

                api_docs_result = {
                    "file_path": api_docs_path,
                    "generated_code": api_docs_content,
                    "content_base64": LangchainService.encode_content(api_docs_content),
                    "file_hash": LangchainService.generate_file_hash(api_docs_content),
                    "entity_name": entity_name,
                }

                # Add API docs to result and write to disk
                result["api_docs"] = api_docs_result

                # Write to disk if not already done
                rel_path = api_docs_path
                if rel_path.replace("\\", "/").startswith(f"repos/{project_id}/"):
                    rel_path = rel_path[len(f"repos/{project_id}/") :].lstrip("/\\")

                self._write_generated_file(project_id, rel_path, api_docs_content)

                # Add to files_to_commit if not already present
                if "files_to_commit" not in result:
                    result["files_to_commit"] = []

                if not any(
                    f["file_path"] == api_docs_path for f in result["files_to_commit"]
                ):
                    result["files_to_commit"].append(
                        {
                            "file_path": rel_path,
                            "generated_code": api_docs_content,
                            "content_base64": api_docs_result["content_base64"],
                            "file_hash": api_docs_result["file_hash"],
                        }
                    )

                await self._notify_event("complete", "api_docs", api_docs_result)
                logger.info("Generated comprehensive API documentation successfully")
            except Exception as e:
                error_msg = f"Error generating API documentation: {str(e)}"
                logger.error(error_msg, exc_info=True)
                await self._notify_info(error_msg)
            try:
                logger.info(f"About to generate Dockerfile for {entity_name}")
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
                logger.info("Generated Dockerfile successfully")
            except Exception as e:
                error_msg = f"Error generating Dockerfile: {str(e)}"
                logger.error(error_msg, exc_info=True)
                await self._notify_info(
                    error_msg
                )  # Step 7.5: TIER 4 - Semantic Validation and Final Quality Analysis
            quality_report = await self._apply_tier4_semantic_validation(
                result, language, project_id, entity_name
            )
            result["quality_report"] = quality_report
            logger.info(
                f"Applied Tier 4 semantic validation - Quality Score: {quality_report.get('overall_score', 'N/A')}"
            )

            # Step 8: Commit files to Git
            git_results = await self._commit_files_to_git(
                project_id, result, language, language_template
            )
            result["git_results"] = (
                git_results  # Step 9: Save endpoint to database if project exists and db session is available
            )
            if project and db is not None:
                await self._save_endpoint_to_db(
                    db, project, result, git_results, request
                )  # Step 10: Generate comprehensive quality recommendations and final report
            try:
                # Extract semantic analysis and architectural report from the quality report
                semantic_analysis = result.get("quality_report", {}).get(
                    "semantic_analysis", {}
                )
                architectural_report = result.get("quality_report", {}).get(
                    "architectural_report", {}
                )

                quality_recommendations = await self._generate_quality_recommendations(
                    semantic_analysis, architectural_report, result
                )
                result["quality_recommendations"] = quality_recommendations
                logger.info("Generated comprehensive quality recommendations")

                # Log final quality summary for monitoring
                overall_score = result.get("quality_report", {}).get("overall_score", 0)
                logger.info(
                    f"Code generation completed with quality score: {overall_score}"
                )

            except Exception as e:
                logger.error(
                    f"Error generating quality recommendations: {str(e)}", exc_info=True
                )

            # Step 11: Create and return response
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
        schema_code: Optional[str] = None,
        model_code: Optional[str] = None,
    ) -> str:
        """
        Generate comprehensive API documentation for an endpoint.
        Includes schema and model information for testing guidance.

        Args:
            project_id: Project identifier
            entity_name: The entity name (singular)
            method: HTTP method
            endpoint_path: API endpoint path
            endpoint_code: Generated endpoint code
            schema_code: Generated schema code (optional)
            model_code: Generated model code (optional)

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
                "schema_code": schema_code or "# No schema code available",
                "model_code": model_code or "# No model code available",
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

        # Initialize files_to_commit list in result
        if "files_to_commit" not in result:
            result["files_to_commit"] = []

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

            # Write model file to disk
            model_file = update_result.get("model_file")
            model_code = update_result.get("content_base64")
            if model_file and model_code:
                import base64

                code = base64.b64decode(model_code).decode("utf-8")
                self._write_generated_file(project_id, model_file, code)
                rel_path = model_file
                if rel_path.replace("\\", "/").startswith(f"repos/{project_id}/"):
                    rel_path = rel_path[len(f"repos/{project_id}/") :].lstrip("/\\")
                result["files_to_commit"].append(
                    {
                        "file_path": rel_path,
                        "generated_code": code,
                        "content_base64": model_code,
                        "file_hash": update_result.get("file_hash"),
                    }
                )
            # Write schema file to disk if updated
            if update_result.get("schema_updated", False):
                schema_file = update_result.get("schema_file")
                schema_code = update_result.get("schema_content_base64")
                if schema_file and schema_code:
                    import base64

                    code = base64.b64decode(schema_code).decode("utf-8")
                    self._write_generated_file(project_id, schema_file, code)
                    rel_path = schema_file
                    if rel_path.replace("\\", "/").startswith(f"repos/{project_id}/"):
                        rel_path = rel_path[len(f"repos/{project_id}/") :].lstrip("/\\")
                    result["files_to_commit"].append(
                        {
                            "file_path": rel_path,
                            "generated_code": code,
                            "content_base64": schema_code,
                            "file_hash": update_result.get("schema_file_hash"),
                        }
                    )
            # Write migration file to disk if present
            if update_result.get("migration"):
                migration = update_result["migration"]
                migration_file = migration.get("file_path")
                migration_code = migration.get("generated_code")
                if migration_file and migration_code:
                    self._write_generated_file(
                        project_id, migration_file, migration_code
                    )
                    rel_path = migration_file
                    if rel_path.replace("\\", "/").startswith(f"repos/{project_id}/"):
                        rel_path = rel_path[len(f"repos/{project_id}/") :].lstrip("/\\")
                    result["files_to_commit"].append(
                        {
                            "file_path": rel_path,
                            "generated_code": migration_code,
                            "content_base64": migration.get("content_base64"),
                            "file_hash": migration.get("file_hash"),
                        }
                    )
            # Also add any files_to_commit from update_result (e.g. binary db files)
            if update_result.get("files_to_commit"):
                for file_info in update_result["files_to_commit"]:
                    rel_path = file_info["file_path"]
                    if rel_path.replace("\\", "/").startswith(f"repos/{project_id}/"):
                        rel_path = rel_path[len(f"repos/{project_id}/") :].lstrip("/\\")
                    # Write file to disk if content is present
                    content = file_info.get("content")
                    if content is not None:
                        binary = file_info.get("is_binary", False)
                        self._write_generated_file(
                            project_id, rel_path, content, binary=binary
                        )
                    # Add to files_to_commit
                    result["files_to_commit"].append(
                        {
                            "file_path": rel_path,
                            "generated_code": file_info.get("content"),
                            "content_base64": file_info.get("content_base64"),
                            "file_hash": file_info.get("file_hash"),
                        }
                    )
        else:
            await self._notify_info(
                f"No updates needed for existing model {entity_name}"
            )

    async def _update_or_append_helpers(
        self,
        project_id: str,
        entity_name: str,
        language_template,
        endpoint_code: str,
        model_code: Optional[str] = None,
        schema_code: Optional[str] = None,
        entity_description: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update or append missing helper functions to the helpers file.

        Args:
            project_id: Project identifier
            entity_name: Name of the entity
            language_template: Template for the target programming language
            endpoint_code: The endpoint code that requires helpers
            model_code: The model code for reference
            schema_code: The schema code for reference
            entity_description: Optional description of the entity

        Returns:
            Dict[str, Any]: Result containing file path and generated code
        """
        try:
            # Get the helpers file path
            component_paths = language_template.get_component_paths(
                project_id=project_id, entity_name=entity_name
            )
            helpers_file_path = component_paths.get("helpers")

            if not helpers_file_path:
                logger.error("No helpers file path found in language template")
                return {"file_path": "", "generated_code": ""}  # Determine language
            file_extension = language_template.get_file_extension()
            language = "python" if file_extension in ("py", ".py") else "javascript"

            # Import the appropriate utility functions
            if language == "python":
                from app.api.v1.utils.code_merge_utils import (
                    extract_py_function_names,
                    extract_required_py_helpers_from_endpoint,
                )

                extract_functions = extract_py_function_names
                extract_required = extract_required_py_helpers_from_endpoint
            else:
                from app.api.v1.utils.code_merge_utils import (
                    extract_js_function_names,
                    extract_required_js_helpers_from_endpoint,
                )

                extract_functions = extract_js_function_names
                extract_required = extract_required_js_helpers_from_endpoint

            # Read existing helpers file if it exists
            full_helpers_path = os.path.join(
                "repos", project_id, helpers_file_path.lstrip("/")
            )
            existing_code = ""
            if os.path.exists(full_helpers_path):
                with open(full_helpers_path, "r", encoding="utf-8") as f:
                    existing_code = (
                        f.read()
                    )  # Find what functions are implemented vs required
            implemented = set(extract_functions(existing_code))
            required = set(extract_required(endpoint_code))

            # IMPORTANT FIX: Don't just subtract implemented from required
            # This would lose helper functions from previous methods on the same endpoint
            # Instead, treat missing as the functions needed by the new endpoint that aren't implemented yet
            missing = required - implemented

            # Maintain a list of all functions that should be in the final helpers file
            # This includes both existing implemented functions AND newly required functions
            all_required_functions = implemented.union(required)

            if not missing:
                logger.info(f"No missing helpers for {entity_name}")
                return {
                    "file_path": helpers_file_path,
                    "generated_code": existing_code,
                    "updated": False,
                }  # Generate only the missing helpers, but preserve the context of all functions            from app.api.v1.services.langchain_service import LangchainService            # We want to generate only the missing functions but need to make sure
            # we're not losing previously implemented functions, so we combine them
            # in the endpoint_code to provide proper context

            # Update endpoint code to include all the required functions
            # This ensures the LLM has context of all functions when generating the missing ones
            if all_required_functions and endpoint_code:
                # If there are existing functions, make sure they're reflected in the endpoint code
                # so the LLM has full context of what's already implemented
                all_funcs_str = ", ".join(all_required_functions)
                # Add a comment to ensure the LLM understands what functions are already implemented
                endpoint_code = f"""
# IMPORTANT: The following helper functions are used across multiple HTTP methods: {all_funcs_str}
# Please ensure all these functions are preserved when generating new helpers.

{endpoint_code}
"""
                logger.info(
                    f"Enhanced endpoint code with all required functions: {all_required_functions}"
                )

            # Call LangchainService with the enhanced context but only generate missing functions
            generated = LangchainService.generate_helpers_sync(
                project_id=project_id,
                entity_name=entity_name,
                entity_description=entity_description,
                endpoint_code=endpoint_code,  # Enhanced with context of all functions
                model_code=model_code or "",
                schema_code=schema_code or "",
                only_functions=list(missing),  # Only generate missing functions
                language=language,
            )

            new_helpers_code = generated.get("generated_code", "")

            # Append new helpers to existing file
            if new_helpers_code:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(full_helpers_path), exist_ok=True)

                with open(full_helpers_path, "a", encoding="utf-8") as f:
                    f.write(new_helpers_code)

                logger.info(
                    f"Appended {len(missing)} missing helper functions to {helpers_file_path}"
                )

                return {
                    "component_type": "helpers",
                    "entity_name": entity_name,
                    "file_path": full_helpers_path,
                    "generated_code": new_helpers_code,
                    "content_base64": LangchainService.encode_content(new_helpers_code),
                    "file_hash": LangchainService.generate_file_hash(new_helpers_code),
                    "appended": os.path.exists(full_helpers_path),
                    "implemented_functions": list(implemented),
                    "required_functions": list(required),
                    "missing_functions": list(missing),
                }
            else:
                logger.warning("No helper code generated")
                return None

        except Exception as e:
            logger.error(f"Error updating helpers: {str(e)}", exc_info=True)
            return None

    async def _process_component_incrementally(
        self,
        component_type: str,
        project_id: str,
        entity_name: str,
        prompt: str,
        language_template,
        generated_code: Dict[str, str],
        method: str,
        endpoint_path: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Process a component type incrementally, handling existing code and dependencies.

        Args:
            component_type: Type of component to process (model, schema, helpers, etc.)
            project_id: Project identifier
            entity_name: Name of the entity
            prompt: The prompt describing what to create
            language_template: Template for the target programming language
            generated_code: Dictionary of already generated code components
            method: HTTP method (GET, POST, etc.)
            endpoint_path: The endpoint path

        Returns:
            Optional[Dict[str, Any]]: Generated component or None if skipped
        """
        try:
            logger.debug(f"Processing {component_type} incrementally for {entity_name}")
            # Special handling for helpers - use incremental update
            if component_type == "helpers":
                return await self._update_or_append_helpers(
                    project_id=project_id,
                    entity_name=entity_name,
                    language_template=language_template,
                    endpoint_code=generated_code.get("endpoint", ""),
                    model_code=generated_code.get("model", ""),
                    schema_code=generated_code.get("schema", ""),
                    entity_description=prompt,
                )
            # For other components, generate normally using the language template
            component = await self._generate_component(
                language_template=language_template,
                component_type=component_type,
                project_id=project_id,
                entity_name=entity_name,
                entity_description=prompt,
                method=method,
                endpoint_path=endpoint_path,
                endpoint_code=generated_code.get("endpoint", ""),
                model_code=generated_code.get("model", ""),
                schema_code=generated_code.get("schema", ""),
            )

            # Ensure the component has the correct structure
            if component and isinstance(component, dict):
                # Make sure required fields are present
                if "file_path" not in component:
                    component_paths = language_template.get_component_paths(
                        project_id=project_id, entity_name=entity_name
                    )
                    component["file_path"] = component_paths.get(component_type, "")

                if "component_type" not in component:
                    component["component_type"] = component_type

                if "entity_name" not in component:
                    component["entity_name"] = entity_name

                logger.debug(
                    f"Successfully processed {component_type} for {entity_name}"
                )
                return component
            else:
                logger.warning(
                    f"Component generation returned invalid result for {component_type}: {type(component)}"
                )
                return None

        except Exception as e:
            logger.error(
                f"Error processing {component_type} incrementally: {str(e)}",
                exc_info=True,
            )
            return None

    async def _check_if_helpers_exist(
        self, project_id: str, entity_name: str, language_template
    ) -> bool:
        """
        Check if helper files already exist for the given entity.

        Args:
            project_id: Project identifier
            entity_name: Name of the entity to check
            language_template: Template for the target programming language

        Returns:
            bool: True if helper files exist, False otherwise
        """
        try:
            # Get the expected helper file path from the template
            helper_paths = language_template.get_component_paths(
                project_id=project_id,
                entity_name=entity_name,
            )

            if "helpers" not in helper_paths:
                logger.debug(f"No helper path defined for {entity_name}")
                return False

            helper_path = helper_paths["helpers"]

            # Check if the file exists
            if os.path.exists(helper_path):
                logger.debug(f"Helper file exists at {helper_path}")
                return True

            # Also check common variations of the helper path
            # For example: helpers/book_helpers.py, utils/book.utils.js, etc.
            possible_paths = [
                helper_path,
                helper_path.replace("helpers", "utils"),
                helper_path.replace("_helpers", ".helpers"),
                helper_path.replace("_helpers", ".utils"),
            ]

            for path in possible_paths:
                if os.path.exists(path):
                    logger.debug(f"Helper file found at alternate path: {path}")
                    return True

            logger.debug(f"No existing helpers found for {entity_name}")
            return False

        except Exception as e:
            logger.error(
                f"Error checking for existing helpers: {str(e)}", exc_info=True
            )
            return False

    async def _analyze_component_dependencies(
        self,
        language_template,
        endpoint_code: str,
        entity_name: str,
        project_id: str,
    ) -> Dict[str, bool]:
        """
        Analyze endpoint code to determine required components and dependencies.

        Args:
            language_template: Template for the target programming language
            endpoint_code: Generated endpoint code to analyze
            entity_name: Name of the entity the endpoint is for
            project_id: Project identifier

        Returns:
            Dict containing analysis results with boolean flags for each dependency
        """
        logger.info(f"Analyzing component dependencies for {entity_name}")

        # Initialize results
        result = {
            "needs_database": False,
            "needs_schema": False,
            "needs_helpers": False,
            "helpers_exist": False,
        }

        # Check for database dependencies
        if hasattr(language_template, "needs_database"):
            result["needs_database"] = language_template.needs_database(endpoint_code)
            logger.debug(f"Database needed: {result['needs_database']}")

        # Check for schema dependencies
        if hasattr(language_template, "needs_schema"):
            result["needs_schema"] = language_template.needs_schema(endpoint_code)
            logger.debug(f"Schema needed: {result['needs_schema']}")

        # Check for helper dependencies
        if hasattr(language_template, "needs_helpers"):
            # First check if the helper is imported or referenced in the code
            result["needs_helpers"] = language_template.needs_helpers(endpoint_code)
            logger.debug(f"Helpers needed: {result['needs_helpers']}")

        # Check if helpers already exist for this entity
        if result["needs_helpers"]:
            result["helpers_exist"] = await self._check_if_helpers_exist(
                project_id, entity_name, language_template
            )
            logger.debug(f"Helpers exist: {result['helpers_exist']}")

        logger.info(f"Dependency analysis for {entity_name}: {result}")
        return result

    async def _should_skip_component(
        self,
        component_type: str,
        dependencies: Dict[str, bool],
        endpoint_component: str,
    ) -> bool:
        """
        Determine if a component should be skipped based on dependency analysis.

        Args:
            component_type: Type of component being processed
            dependencies: Dictionary of analyzed dependencies
            endpoint_component: Name of the endpoint component type

        Returns:
            bool: True if component should be skipped, False otherwise
        """
        if component_type == endpoint_component:
            # Skip the primary endpoint component since it's already generated
            return True

        if component_type == "model" and not dependencies["needs_database"]:
            logger.debug(f"Skipping {component_type} - no database dependency")
            return True

        if component_type == "migration" and not dependencies["needs_database"]:
            logger.debug(f"Skipping {component_type} - no database dependency")
            return True

        if component_type == "schema" and not dependencies["needs_schema"]:
            logger.debug(f"Skipping {component_type} - no schema dependency")
            return True

        if component_type == "helpers" and not dependencies["needs_helpers"]:
            logger.debug(f"Skipping {component_type} - no helper dependency")
            return True

        return False

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
            # Check if the language template supports migration generation
            if not hasattr(language_template, "generate_migration"):
                logger.info(
                    "Migration generation not supported for this language template"
                )
                return result  # Generate migration using the language template
            migration_result = await language_template.generate_migration(
                project_dir=project_dir, entity_name=entity_name
            )

            if migration_result and migration_result.get("generated_code"):
                result["migration"] = migration_result

                # Add migration files to commit list if they exist
                migration_path = migration_result.get("file_path")
                if migration_path and os.path.exists(migration_path):
                    if "files_to_commit" not in result:
                        result["files_to_commit"] = []

                    result["files_to_commit"].append(
                        {
                            "file_path": migration_path,
                            "content_base64": migration_result.get(
                                "content_base64", ""
                            ),
                            "file_hash": migration_result.get("file_hash", ""),
                        }
                    )

                logger.info(f"Successfully generated migration for {entity_name}")
            else:
                logger.warning(f"Migration generation failed for {entity_name}")

        except Exception as e:
            logger.error(
                f"Error generating migration for {entity_name}: {str(e)}", exc_info=True
            )

        return result

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
        if hasattr(language_template, "extract_entity_from_prompt"):
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
        Generate new components based on the primary component and dependencies.

        Args:
            result: Dictionary to store generated components
            language_template: Template for the target programming language
            project_id: Project identifier
            entity_name: Name of the entity
            prompt: User's prompt describing desired functionality
            primary_component: The primary component (usually endpoint) that's already generated
            method: HTTP method for the endpoint
            endpoint_path: URL path for the endpoint
        """
        try:
            # Get the endpoint code for dependency analysis
            endpoint_code = primary_component.get("generated_code", "")

            # Analyze what components are needed
            dependencies = await self._analyze_component_dependencies(
                language_template, endpoint_code, entity_name, project_id
            )

            # Get the list of required components from the template
            required_components = language_template.get_required_components()
            endpoint_component = primary_component.get("component_type", "endpoint")

            # Process each component type
            for component_type in required_components:
                try:
                    # Check if we should skip this component
                    should_skip = await self._should_skip_component(
                        component_type, dependencies, endpoint_component
                    )

                    if should_skip:
                        logger.debug(f"Skipping {component_type} for {entity_name}")
                        continue
                    # Process the component incrementally
                    component_result = await self._process_component_incrementally(
                        component_type=component_type,
                        project_id=project_id,
                        entity_name=entity_name,
                        prompt=prompt,
                        language_template=language_template,
                        generated_code={endpoint_component: endpoint_code},
                        method=method,
                        endpoint_path=endpoint_path,
                    )

                    # Apply Tier 2 & 3 Quality Processing to each generated component
                    if component_result and "generated_code" in component_result:
                        language_str = getattr(language_template, "language", "python")
                        component_result = (
                            await self._apply_tier2_tier3_quality_processing(
                                component_result, language_str, project_id, entity_name
                            )
                        )
                        logger.info(
                            f"Applied Tier 2 & 3 quality processing to {component_type}"
                        )

                    if component_result:
                        result[component_type] = component_result
                        logger.info(
                            f"Successfully generated {component_type} for {entity_name}"
                        )
                    else:
                        logger.warning(f"No result generated for {component_type}")

                except Exception as e:
                    logger.error(
                        f"Error generating {component_type}: {str(e)}", exc_info=True
                    )
                    continue

            # Generate migration if database components were created
            if dependencies.get("needs_database", False):
                try:
                    await self._generate_migration(
                        project_id, entity_name, result, language_template
                    )
                except Exception as e:
                    logger.error(f"Error generating migration: {str(e)}", exc_info=True)

        except Exception as e:
            logger.error(f"Error in _generate_new_components: {str(e)}", exc_info=True)
            raise

    async def _update_component_with_unified_entity(
        self,
        component: Dict[str, Any],
        old_entity_name: str,
        new_entity_name: str,
        language_template,
    ) -> Dict[str, Any]:
        """
        Update a component's code to use the new unified entity name.

        Args:
            component: The component to update
            old_entity_name: The old entity name to replace
            new_entity_name: The new entity name to use
            language_template: The language template for specific transformations

        Returns:
            Dict[str, Any]: The updated component
        """
        try:
            if not component or not component.get("generated_code"):
                return component

            updated_code = component["generated_code"]

            # Replace entity name references in the code
            # Handle PascalCase
            updated_code = updated_code.replace(old_entity_name, new_entity_name)

            # Handle snake_case
            old_snake = self._to_snake_case(old_entity_name)
            new_snake = self._to_snake_case(new_entity_name)
            updated_code = updated_code.replace(old_snake, new_snake)

            # Handle lowercase
            updated_code = updated_code.replace(
                old_entity_name.lower(), new_entity_name.lower()
            )

            # Update the component
            component["generated_code"] = updated_code
            component["entity_name"] = new_entity_name

            # Regenerate hash and base64 content
            from app.api.v1.services.langchain_service import LangchainService

            component["content_base64"] = LangchainService.encode_content(updated_code)
            component["file_hash"] = LangchainService.generate_file_hash(updated_code)

            logger.info(f"Updated component to use entity name: {new_entity_name}")
            return component

        except Exception as e:
            logger.error(
                f"Error updating component with unified entity: {str(e)}", exc_info=True
            )
            return component

    async def _notify_info(self, message: str) -> None:
        """
        Send an information message via the callback if available.

        Args:
            message: The information message to send
        """
        if self.on_info:
            try:
                await self.on_info(message)
            except Exception as e:
                logger.error(f"Error in info callback: {str(e)}", exc_info=True)

    async def _notify_event(
        self, event_type: str, component_type: str, data: Dict[str, Any]
    ) -> None:
        """
        Send an event notification via the appropriate callback if available.

        Args:
            event_type: Type of event ('start' or 'complete')
            component_type: Type of component being processed
            data: Additional data to send with the event
        """
        try:
            if event_type == "start" and component_type in self.on_component_start:
                callback = self.on_component_start[component_type]
                if callback:
                    await callback(component_type, data)
            elif (
                event_type == "complete"
                and component_type in self.on_component_complete
            ):
                callback = self.on_component_complete[component_type]
                if callback:
                    await callback(component_type, data)
        except Exception as e:
            logger.error(
                f"Error in event callback for {event_type} {component_type}: {str(e)}",
                exc_info=True,
            )

    async def _generate_component(
        self,
        language_template: Any,
        component_type: str,
        project_id: int,
        entity_name: str,
        entity_description: str,
        method: str,
        endpoint_path: str,
        endpoint_code: str = "",
        model_code: str = "",
        schema_code: str = "",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generate a specific component using the language template.

        Args:
            language_template: The language template to use for generation
            component_type: Type of component to generate
            project_id: ID of the project
            entity_name: Name of the entity
            entity_description: Description of the entity
            method: HTTP method
            endpoint_path: API endpoint path
            endpoint_code: Generated endpoint code (if available)
            model_code: Generated model code (if available)
            schema_code: Generated schema code (if available)
            **kwargs: Additional keyword arguments

        Returns:
            Dict[str, Any]: Generated component data
        """
        try:
            # Notify start of component generation
            await self._notify_event(
                "start",
                component_type,
                {"entity_name": entity_name, "component_type": component_type},
            )

            # Use the language template to generate the component
            if hasattr(language_template, "generate_component"):
                component = await language_template.generate_component(
                    component_type=component_type,
                    project_id=project_id,
                    entity_name=entity_name,
                    entity_description=entity_description,
                    method=method,
                    endpoint_path=endpoint_path,
                    endpoint_code=endpoint_code,
                    model_code=model_code,
                    schema_code=schema_code,
                    **kwargs,
                )
            else:
                # Fallback to individual component generation methods
                method_name = f"generate_{component_type}"
                if hasattr(language_template, method_name):
                    generate_method = getattr(language_template, method_name)
                    component = await generate_method(
                        project_id=project_id,
                        entity_name=entity_name,
                        entity_description=entity_description,
                        method=method,
                        endpoint_path=endpoint_path,
                        endpoint_code=endpoint_code,
                        model_code=model_code,
                        schema_code=schema_code,
                        **kwargs,
                    )
                else:
                    raise ValueError(
                        f"Component type '{component_type}' not supported by language template"
                    )

            # Notify completion of component generation
            await self._notify_event("complete", component_type, component)

            return component

        except Exception as e:
            error_msg = f"Error generating {component_type} component: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await self._notify_info(error_msg)
            raise

    async def _commit_files_to_git(
        self,
        project_id: int,
        result: Dict[str, Any],
        language: str,
        language_template: Any,
    ) -> Dict[str, Any]:
        """
        Commit generated files to Git repository if enabled.

        Args:
            project_id: ID of the project
            result: Generation result containing file information
            language: Programming language used
            language_template: Language template used for generation

        Returns:
            Dict[str, Any]: Git operation results
        """
        git_results = {"success": False, "message": "Git operations disabled"}

        try:
            # Check if git operations are enabled (this could be a configuration setting)
            git_enabled = getattr(language_template, "git_enabled", False)

            if not git_enabled:
                git_results["message"] = "Git operations not enabled for this template"
                return git_results

            # Get project directory
            project_dir = getattr(language_template, "project_directory", None)
            if not project_dir:
                git_results["message"] = "Project directory not found"
                return git_results

            # Check if directory is a git repository
            git_dir = Path(project_dir) / ".git"
            if not git_dir.exists():
                git_results["message"] = "Not a git repository"
                return git_results

            # Prepare commit message
            entity_name = result.get("entity_name", "unknown")
            components = []
            for key in ["endpoint", "model", "schema", "helpers", "migration"]:
                if key in result and result[key]:
                    components.append(key)
            commit_message = f"Add {language} {', '.join(components)} for {entity_name}"

            # Add files to git using actual GitService operations
            files_added = []
            files_to_commit = []

            for component_type, component_data in result.items():
                if isinstance(component_data, dict) and "file_path" in component_data:
                    file_path = component_data["file_path"]
                    files_added.append(file_path)

                    # Read the generated code content
                    generated_code = component_data.get("generated_code", "")
                    if generated_code:
                        files_to_commit.append(
                            {"file_path": file_path, "content": generated_code}
                        )  # Commit files using GitService
            if files_to_commit:
                from app.api.v1.services.git_service import GitService

                try:
                    # First, write all files to disk
                    for file_data in files_to_commit:
                        file_path = file_data["file_path"]
                        content = file_data["content"]

                        # Ensure the file is written to the correct location
                        full_file_path = Path(project_dir) / file_path
                        full_file_path.parent.mkdir(parents=True, exist_ok=True)

                        with open(full_file_path, "w", encoding="utf-8") as f:
                            f.write(content)

                    # Extract just the file paths for the GitService call
                    file_paths = [
                        file_data["file_path"] for file_data in files_to_commit
                    ]

                    # Commit multiple files at once using the correct method name
                    commit_result = await GitService.commit_multiple_files_update(
                        project_id=str(project_id),
                        file_paths=file_paths,
                        commit_message=commit_message,
                    )

                    git_results = {
                        "success": True,
                        "message": f"Successfully committed {len(files_added)} files to Git",
                        "commit_message": commit_message,
                        "files_added": files_added,
                        "commit_id": commit_result,
                    }
                except Exception as e:
                    logger.error(f"Error committing files with GitService: {str(e)}")
                    git_results = {
                        "success": False,
                        "message": f"Failed to commit files: {str(e)}",
                        "commit_message": commit_message,
                        "files_added": files_added,
                        "error": str(e),
                    }
            else:
                git_results = {
                    "success": False,
                    "message": "No files to commit",
                    "commit_message": commit_message,
                    "files_added": files_added,
                }

            await self._notify_info(f"Git: {git_results['message']}")

        except Exception as e:
            error_msg = f"Error committing files to git: {str(e)}"
            logger.error(error_msg, exc_info=True)
            git_results = {"success": False, "message": error_msg, "error": str(e)}

        return git_results

    def _to_snake_case(self, name: str) -> str:
        """
        Convert a name to snake_case.

        Args:
            name: The name to convert

        Returns:
            str: The name in snake_case
        """
        if not name:
            return ""

        # Insert underscores before uppercase letters (except the first)
        result = ""
        for i, char in enumerate(name):
            if i > 0 and char.isupper():
                result += "_"
            result += char.lower()

        return result

    def _write_generated_file(
        self, project_id: str, file_path: str, content: str, binary: bool = False
    ) -> None:
        """
        Write generated code content to a file on disk within the project directory.

        This method handles writing generated files to the correct location within the
        repos/{project_id}/ directory structure. It creates necessary directories
        and handles both text and binary content.

        Args:
            project_id (str): The project identifier
            file_path (str): The relative path to the file within the project
            content (str or bytes): The content to write to the file
            binary (bool): Whether the content is binary data (default: False)

        Returns:
            None
        """
        try:
            # Normalize the file path - remove leading/trailing slashes and backslashes
            normalized_path = file_path.strip("/\\").replace("\\", "/")

            # If the path already starts with repos/{project_id}/, use it as is
            if normalized_path.startswith(f"repos/{project_id}/"):
                full_path = normalized_path
            else:
                # Otherwise, prepend the repos/{project_id}/ prefix
                full_path = f"repos/{project_id}/{normalized_path}"

            # Create parent directories if they don't exist (using os.makedirs for compatibility with mocks)
            import os

            parent_dir = os.path.dirname(full_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            # Write the content to the file (using builtin open to work with test mocks)
            if binary:
                # Handle binary content (bytes)
                if isinstance(content, str):
                    content = content.encode("utf-8")
                with open(full_path, "wb") as f:
                    f.write(content)
                logger.debug(f"Wrote binary file to {full_path}")
            else:
                # Handle text content
                if isinstance(content, bytes):
                    content = content.decode("utf-8")
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                logger.debug(f"Wrote text file to {full_path}")

        except Exception as e:
            error_msg = f"Error writing file {file_path}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise Exception(error_msg)

    async def _check_for_existing_model(
        self, project_id: str, entity_name: str
    ) -> bool:
        """
        Check if a model already exists for the given entity.

        Args:
            project_id: Project identifier
            entity_name: Name of the entity to check

        Returns:
            bool: True if an existing model is found, False otherwise
        """
        try:
            # Use ProjectAnalysisService to analyze the project and find models
            from app.api.v1.services.project_analysis_service import (
                ProjectAnalysisService,
            )

            project_analysis = await ProjectAnalysisService.analyze_project(
                project_id, language="python"  # Default to python for now
            )

            models = project_analysis.get("models", [])

            if not models:
                logger.debug(f"No models found in project {project_id}")
                return False
            # Generate variations of the entity name for flexible matching
            entity_variations = [
                entity_name.lower(),
                entity_name.lower() + "s",
                entity_name.lower().rstrip("s"),
                entity_name.lower() + "model",
                entity_name.lower().replace("_", ""),
            ]

            logger.debug(f"Checking for existing model for entity: {entity_name}")
            logger.debug(f"Entity variations: {entity_variations}")
            logger.debug(f"Available models: {[m.get('name', '') for m in models]}")

            # Search for matching model
            for model in models:
                model_name = model.get("name", "").lower()

                # Check for direct match
                if model_name in entity_variations:
                    logger.info(
                        f"Found existing model: {model.get('name')} matches entity: {entity_name}"
                    )
                    return True

                # Check if entity name is contained in model name or vice versa
                if any(
                    var in model_name or model_name in var for var in entity_variations
                ):
                    logger.info(
                        f"Found existing model: {model.get('name')} partially matches entity: {entity_name}"
                    )
                    return True

            logger.debug(f"No existing model found for entity: {entity_name}")
            return False

        except Exception as e:
            logger.error(f"Error checking for existing model: {str(e)}", exc_info=True)
            return False

    async def _write_all_components_to_disk(
        self, result: Dict[str, Any], project_id: str, language: str, entity_name: str
    ) -> None:
        """
        Write all generated components to disk with Tier 4 semantic validation.

        Args:
            result: Dictionary containing all generated components
            project_id: Project identifier
            language: Programming language (e.g., "python", "javascript")
            entity_name: Name of the entity being processed
        """
        try:
            components_to_write = [
                "model",
                "schema",
                "helpers",
                "migration",
            ]  # TIER 4: Apply Semantic Validation before writing to disk
            await self._apply_tier4_semantic_validation(
                result, language, project_id, entity_name
            )
            logger.info("Applied Tier 4 semantic validation to all components")

            for component_type in components_to_write:
                if component_type in result and result[component_type]:
                    component = result[component_type]

                    if (
                        isinstance(component, dict)
                        and "file_path" in component
                        and "generated_code" in component
                    ):
                        file_path = component["file_path"]
                        generated_code = component["generated_code"]

                        # Normalize to relative path
                        rel_path = file_path
                        if rel_path.replace("\\", "/").startswith(
                            f"repos/{project_id}/"
                        ):
                            rel_path = rel_path[len(f"repos/{project_id}/") :].lstrip(
                                "/\\"
                            )
                            component["file_path"] = rel_path

                        # Write the component to disk
                        logger.info(
                            f"Writing {component_type} component to disk: {rel_path}"
                        )
                        self._write_generated_file(project_id, rel_path, generated_code)

                        # Initialize files_to_commit if not present
                        if "files_to_commit" not in result:
                            result["files_to_commit"] = []

                        # Add component to files_to_commit if not already present
                        if not any(
                            f.get("file_path") == rel_path
                            for f in result["files_to_commit"]
                        ):
                            result["files_to_commit"].append(
                                {
                                    "file_path": rel_path,
                                    "generated_code": generated_code,
                                    "content_base64": component.get("content_base64"),
                                    "file_hash": component.get("file_hash"),
                                }
                            )

                        logger.info(
                            f"Successfully wrote {component_type} component to {rel_path}"
                        )

        except Exception as e:
            logger.error(f"Error writing components to disk: {str(e)}", exc_info=True)

    # =============================================================================
    # FOUR-TIER QUALITY STRATEGY IMPLEMENTATION
    # ============================================================================

    async def _apply_tier1_prompt_enhancement(
        self,
        prompt: str,
        language: str,
        project_id: str,
        additional_context: Optional[str] = None,
    ) -> str:
        """
        TIER 1: Prompt Enhancement (Prevention-First Quality Strategy)

        Enhance the original prompt with quality best practices, context,
        and error prevention patterns before code generation begins.

        Args:
            prompt: Original user prompt
            language: Target programming language
            project_id: Project identifier for context
            additional_context: Optional additional context

        Returns:
            str: Enhanced prompt with quality guidelines
        """
        try:
            logger.info("Applying Tier 1: Prompt Enhancement")

            # Get quality configuration for this project
            quality_config = self.quality_config_manager.get_config(
                project_id=project_id, level=QualityConfigLevel.ENHANCED
            )  # Use enhanced quality middleware for prompt enhancement
            enhanced_prompt = await self.enhanced_quality_middleware.enhance_prompt(
                original_prompt=prompt,
                language=language,
                context={
                    "project_id": project_id,
                    "additional_context": additional_context,
                    "quality_config": quality_config,
                },
            )

            # Collect metrics
            self.quality_metrics_collector.record_prompt_enhancement(
                project_id=project_id,
                original_length=len(prompt),
                enhanced_length=len(enhanced_prompt),
                language=language,
            )

            logger.info(
                f"Prompt enhanced from {len(prompt)} to {len(enhanced_prompt)} characters"
            )
            return enhanced_prompt

        except Exception as e:
            logger.error(f"Error in Tier 1 prompt enhancement: {str(e)}")
            # Return original prompt if enhancement fails
            return prompt

    async def _apply_tier2_tier3_quality_processing(
        self,
        component: Dict[str, Any],
        language: str,
        project_id: str,
        entity_name: str,
    ) -> Dict[str, Any]:
        """
        TIER 2 & 3: Real-time Validation + Automated Code Quality (Auto-fixing)

        Apply real-time validation during generation and automatic code quality
        improvements including formatting, linting, and security analysis.

        Args:
            component: Generated component with code
            language: Target programming language
            project_id: Project identifier
            entity_name: Entity being processed

        Returns:
            Dict[str, Any]: Component with enhanced and validated code
        """
        try:
            logger.info(
                f"Applying Tier 2 & 3: Real-time Validation + Auto-fixing for {entity_name}"
            )

            if not component.get("generated_code"):
                logger.warning(
                    "No generated code found in component for quality processing"
                )
                return component

            original_code = component["generated_code"]

            # TIER 2: Real-time Validation
            validation_result = (
                await self.enhanced_quality_middleware.validate_realtime(
                    code=original_code,
                    language=language,
                    context={
                        "project_id": project_id,
                        "entity_name": entity_name,
                        "component_type": component.get("component_type", "unknown"),
                    },
                )
            )

            # TIER 3: Auto-fixing and Quality Enhancement
            enhanced_code = await self.enhanced_quality_middleware.process_code_quality(
                code=validation_result.get("validated_code", original_code),
                language=language,
                quality_level=QualityLevel.ENHANCED,
                context={
                    "project_id": project_id,
                    "entity_name": entity_name,
                    "validation_issues": validation_result.get("issues", []),
                },
            )

            # Update component with enhanced code
            component["generated_code"] = enhanced_code.get(
                "enhanced_code", original_code
            )

            # Add quality metadata
            component["quality_metadata"] = {
                "tier2_validation": validation_result,
                "tier3_enhancement": enhanced_code,
                "quality_score": enhanced_code.get("quality_score", 0),
                "improvements_applied": enhanced_code.get("improvements", []),
            }

            # Collect metrics
            self.quality_metrics_collector.record_code_processing(
                project_id=project_id,
                component_type=component.get("component_type", "unknown"),
                original_lines=len(original_code.splitlines()),
                enhanced_lines=len(component["generated_code"].splitlines()),
                quality_score=enhanced_code.get("quality_score", 0),
                improvements_count=len(enhanced_code.get("improvements", [])),
            )

            logger.info(
                f"Applied Tier 2 & 3 processing - Quality Score: {enhanced_code.get('quality_score', 'N/A')}"
            )
            return component

        except Exception as e:
            logger.error(f"Error in Tier 2 & 3 quality processing: {str(e)}")
            # Return original component if processing fails
            return component

    async def _apply_tier4_semantic_validation(
        self,
        result: Dict[str, Any],
        language: str,
        project_id: str,
        entity_name: str,
    ) -> Dict[str, Any]:
        """
        TIER 4: Semantic Validation (Deep Analysis)

        Perform comprehensive semantic analysis of all generated components,
        including architectural compliance, integration testing, and performance analysis.

        Args:
            result: Complete generation result with all components
            language: Target programming language
            project_id: Project identifier
            entity_name: Entity being processed

        Returns:
            Dict[str, Any]: Comprehensive quality report
        """
        try:
            logger.info(f"Applying Tier 4: Semantic Validation for {entity_name}")

            # Collect all generated code for analysis
            all_components = {}
            for component_type, component_data in result.items():
                if (
                    isinstance(component_data, dict)
                    and "generated_code" in component_data
                ):
                    all_components[component_type] = component_data["generated_code"]

            # Perform semantic validation using enhanced middleware
            semantic_analysis = (
                await self.enhanced_quality_middleware.perform_semantic_validation(
                    components=all_components,
                    language=language,
                    context={
                        "project_id": project_id,
                        "entity_name": entity_name,
                        "generation_metadata": {
                            "component_count": len(all_components),
                            "database_usage": result.get(
                                "detected_database_usage", False
                            ),
                        },
                    },
                )
            )  # Generate architectural compliance report
            architectural_report = (
                await self.enhanced_quality_middleware.validate_architecture(
                    components=all_components,
                    language=language,
                    context={"project_id": project_id},
                )
            )

            # Create comprehensive quality report
            quality_report = {
                "overall_score": semantic_analysis.get("overall_score", 0),
                "semantic_analysis": semantic_analysis,
                "architectural_compliance": architectural_report,
                "component_scores": {},
                "recommendations": [],
                "validation_timestamp": self._get_current_timestamp(),
            }

            # Calculate individual component scores
            for component_type, component_data in result.items():
                if (
                    isinstance(component_data, dict)
                    and "quality_metadata" in component_data
                ):
                    quality_report["component_scores"][component_type] = {
                        "score": component_data["quality_metadata"].get(
                            "quality_score", 0
                        ),
                        "improvements": len(
                            component_data["quality_metadata"].get(
                                "improvements_applied", []
                            )
                        ),
                    }

            # Generate quality recommendations
            recommendations = await self._generate_quality_recommendations(
                semantic_analysis, architectural_report, result
            )
            quality_report["recommendations"] = recommendations  # Collect final metrics
            try:
                semantic_metrics = {
                    "total_duration": 0.0,
                    "lines_of_code": sum(
                        len(comp.get("generated_code", "").split("\n"))
                        for comp in all_components.values()
                    ),
                    "functions_count": len(all_components),
                    "classes_count": len(
                        [
                            comp
                            for comp in all_components.values()
                            if "class " in comp.get("generated_code", "")
                        ]
                    ),
                    "complexity_score": quality_report["overall_score"],
                }

                pipeline_result = {
                    "quality_score": quality_report["overall_score"],
                    "total_issues": len(quality_report.get("issues", [])),
                    "critical_issues": len(
                        [
                            issue
                            for issue in quality_report.get("issues", [])
                            if issue.get("severity") == "critical"
                        ]
                    ),
                    "high_issues": len(
                        [
                            issue
                            for issue in quality_report.get("issues", [])
                            if issue.get("severity") == "high"
                        ]
                    ),
                    "medium_issues": len(
                        [
                            issue
                            for issue in quality_report.get("issues", [])
                            if issue.get("severity") == "medium"
                        ]
                    ),
                    "low_issues": len(
                        [
                            issue
                            for issue in quality_report.get("issues", [])
                            if issue.get("severity") == "low"
                        ]
                    ),
                    "issues_fixed": 0,
                    "tiers": {
                        "tier4": {
                            "duration": 0.0,
                            "score": quality_report["overall_score"],
                        }
                    },
                }

                self.quality_metrics_collector.collect_metrics(
                    project_id=project_id,
                    language=language,
                    quality_level="comprehensive",
                    pipeline_result=pipeline_result,
                    execution_stats=semantic_metrics,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to collect semantic validation metrics: {str(e)}"
                )

            # Log quality summary
            logger.info(
                f"Tier 4 validation complete - Overall Score: {quality_report['overall_score']}/100"
            )
            if recommendations:
                logger.info(f"Generated {len(recommendations)} quality recommendations")

            return quality_report

        except Exception as e:
            logger.error(f"Error in Tier 4 semantic validation: {str(e)}")
            return {
                "overall_score": 0,
                "error": str(e),
                "validation_timestamp": self._get_current_timestamp(),
            }

    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        from datetime import datetime

        return datetime.now().isoformat()

    async def _generate_quality_recommendations(
        self,
        semantic_analysis: Dict[str, Any],
        architectural_report: Dict[str, Any],
        result: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Generate actionable quality recommendations based on analysis results.

        Args:
            semantic_analysis: Results from semantic validation
            architectural_report: Results from architectural compliance check
            result: Complete generation result

        Returns:
            List[Dict[str, Any]]: List of quality recommendations
        """
        try:
            recommendations = []

            # Add semantic analysis recommendations
            if semantic_analysis.get("issues"):
                for issue in semantic_analysis["issues"]:
                    recommendations.append(
                        {
                            "priority": issue.get("severity", "medium"),
                            "category": "semantic",
                            "title": issue.get("title", "Semantic Issue"),
                            "description": issue.get("description", ""),
                            "suggested_fix": issue.get("suggestion", ""),
                            "component": issue.get("component", "unknown"),
                        }
                    )

            # Add architectural recommendations
            if architectural_report.get("violations"):
                for violation in architectural_report["violations"]:
                    recommendations.append(
                        {
                            "priority": "high",
                            "category": "architecture",
                            "title": f"Architectural Violation: {violation.get('rule', 'Unknown')}",
                            "description": violation.get("description", ""),
                            "suggested_fix": violation.get("fix_suggestion", ""),
                            "component": violation.get("component", "unknown"),
                        }
                    )

            # Add performance recommendations
            if semantic_analysis.get("performance_score", 100) < 80:
                recommendations.append(
                    {
                        "priority": "medium",
                        "category": "performance",
                        "title": "Performance Optimization Opportunity",
                        "description": "Generated code may benefit from performance optimizations",
                        "suggested_fix": "Review database queries, add appropriate indexes, optimize algorithms",
                        "component": "all",
                    }
                )

            # Add security recommendations
            if semantic_analysis.get("security_score", 100) < 90:
                recommendations.append(
                    {
                        "priority": "high",
                        "category": "security",
                        "title": "Security Enhancement Needed",
                        "description": "Security best practices should be applied",
                        "suggested_fix": "Add input validation, implement proper authentication, sanitize data",
                        "component": "all",
                    }
                )

            return recommendations

        except Exception as e:
            logger.error(f"Error generating quality recommendations: {str(e)}")
            return []
