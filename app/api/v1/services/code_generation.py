import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from app.api.v1.schemas.code_generation import (
    CodeGenerationRequest,
    CodeGenerationResponse,
    GenerationResult,
)
from app.api.v1.services.git_service import GitService
from app.api.v1.services.langchain_service import LangchainService
from app.api.v1.services.language_templates import LanguageTemplateFactory
from app.api.v1.services.llm_service import LLMService
from app.api.v1.services.model_schema_update_service import ModelSchemaManager
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
        }

        # Add non-None callbacks to component callbacks
        for component, callback in legacy_start_mapping.items():
            if callback and component not in self.on_component_start:
                self.on_component_start[component] = callback

        for component, callback in legacy_complete_mapping.items():
            if callback and component not in self.on_component_complete:
                self.on_component_complete[component] = callback

    async def generate_code(
        self, request: CodeGenerationRequest
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

            # Initialize language template
            language_template = LanguageTemplateFactory.get_template(language)

            # Log generation start
            logger.info(f"Generating code in {language} for: {prompt}")
            await self._notify_info(
                f"Starting code generation in {language} for: {prompt}"
            )

            # Step 1: Generate primary endpoint/controller
            primary_component = await self._generate_primary_component(
                language_template,
                project_id,
                prompt,
                method,
                endpoint_path,
                request.additional_context,
            )

            # Step 2: Determine if database components are needed
            needs_database = language_template.needs_database(
                primary_component.get("generated_code", "")
            )

            # Step 3: Extract entity name
            entity_name = self._extract_entity_name(
                language_template, primary_component
            )
            primary_component["entity_name"] = entity_name

            # Update file path with correct entity name
            component_type = language_template.get_component_map().get("endpoint")
            primary_component["file_path"] = language_template.get_component_paths(
                project_id, entity_name
            )[component_type]

            # Step 4: Initialize result dictionary
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
                    # Handle model updates
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
                    # Generate new components
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

            # Step 6: Commit files to Git
            git_results = await self._commit_files_to_git(
                project_id, result, language, language_template
            )
            result["git_results"] = git_results

            # Step 7: Create and return response
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

    async def _generate_primary_component(
        self,
        language_template,
        project_id,
        prompt,
        method,
        endpoint_path,
        additional_context,
    ):
        """
        Generate the primary component (endpoint/controller) for the requested feature.

        This method creates the main entry point component (such as an API endpoint,
        controller, or route handler) based on the user's prompt and selected language.

        Args:
            language_template: Template for the target programming language
            project_id: Identifier for the project being modified
            prompt: Natural language description of the desired functionality
            method: HTTP method for the endpoint (GET, POST, etc.)
            endpoint_path: URL path for the endpoint
            additional_context: Any supplementary information to guide generation

        Returns:
            Dict: Component data including generated code, file path, and metadata

        Raises:
            ValueError: If the selected language doesn't support endpoints/controllers
        """
        # Get the endpoint component type for this language
        endpoint_component = language_template.get_component_map().get("endpoint")
        if not endpoint_component:
            raise ValueError("Language does not support endpoints/controllers")

        # Generate the component
        return await self._generate_component(
            language_template,
            endpoint_component,
            project_id,
            "temp",
            prompt,
            method=method,
            endpoint_path=endpoint_path,
            additional_context=additional_context,
        )

    def _extract_entity_name(self, language_template, primary_component):
        """
        Extract entity name from the generated code using language-specific extraction rules.

        This method analyzes the primary component code to determine the main entity
        name (e.g., User, Product, Order) that the generated code is operating on.
        This entity name is used for naming all related components.

        Args:
            language_template: Template for the target programming language
            primary_component: Dictionary containing the generated primary component

        Returns:
            str: The extracted entity name or "User" as a fallback if extraction fails
        """
        extracted_name = language_template.extract_entity_from_code(
            primary_component.get("generated_code", "")
        )
        return extracted_name or "User"

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

        This method checks for an existing model and determines if updates are needed based
        on the new endpoint's requirements. If updates are needed, it generates schema changes
        and migrations to accommodate the new functionality while preserving existing data.

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

        # Process potential model updates
        update_result = await self._check_and_update_existing_model(
            project_id=project_id,
            entity_name=entity_name,
            prompt_description=prompt,
            endpoint_code=primary_component.get("generated_code", ""),
            language=language,
        )

        if update_result and update_result.get("model_updated", False):
            # Model was updated
            await self._notify_info(f"Updated existing model {entity_name}")
            await self._process_model_updates(
                result, update_result, entity_name, project_id, language
            )
        else:
            await self._notify_info(
                f"No updates needed for existing model {entity_name}"
            )

    async def _process_model_updates(
        self, result, update_result, entity_name, project_id, language
    ):
        """
        Process model updates and add them to the result dictionary.

        This method handles the results of model updates, including updating the
        model itself, schemas, and generating migrations when necessary.

        Args:
            result: Dictionary to store generation results
            update_result: Dictionary containing model update details
            entity_name: Name of the entity being updated
            project_id: Identifier for the project being modified

        Returns:
            None: Results are added directly to the result dictionary
        """
        # Add model update details
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
            # Get the schema code from the update result
            schema_code = update_result.get(
                "schema_code", "# Updated schema code not available"
            )
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
        else:
            placeholder_schema = f"# No updates needed for the schema of {entity_name}"
            result["schema"] = {
                "file_path": f"schemas/{entity_name.lower()}{LangchainService.get_file_extension(language)}",
                "generated_code": placeholder_schema,
                "content_base64": LangchainService.encode_content(placeholder_schema),
                "file_hash": LangchainService.generate_file_hash(placeholder_schema),
                "exists": True,
                "updated": False,
                "entity_name": entity_name,
            }

        # Add migration if it was generated during the update
        if update_result.get("migration"):
            result["migration"] = update_result.get("migration")

            if (
                "file_hash" not in result["migration"]
                and "generated_code" in result["migration"]
            ):
                result["migration"]["file_hash"] = LangchainService.generate_file_hash(
                    result["migration"]["generated_code"]
                )
            if (
                "content_base64" not in result["migration"]
                and "generated_code" in result["migration"]
            ):
                result["migration"]["content_base64"] = LangchainService.encode_content(
                    result["migration"]["generated_code"]
                )

        # Process files to commit from the update
        if update_result.get("files_to_commit"):
            await self._commit_updated_files(
                project_id, update_result.get("files_to_commit")
            )

    async def _generate_new_components(
        self,
        result,
        language_template,
        project_id,
        entity_name,
        prompt,
        primary_component,
        method,
        endpoint_path,
    ):
        """
        Generate new components for an entity that doesn't already exist in the project.

        This method creates all necessary components for a new entity based on the
        language template's requirements. This typically includes models, schemas,
        validation rules, helper functions, and migrations as appropriate for the language.

        Args:
            result: Dictionary to store generation results
            language_template: Template for the target programming language
            project_id: Identifier for the project being modified
            entity_name: Name of the entity to create
            prompt: Natural language description of the desired functionality
            primary_component: Dictionary containing the generated primary component
            method: HTTP method for the endpoint (GET, POST, etc.)
            endpoint_path: URL path for the endpoint

        Returns:
            None: Results are added directly to the result dictionary
        """
        await self._notify_info(f"Generating new components for {entity_name}")

        # Get required components for this language
        required_components = language_template.get_required_components()
        endpoint_component = language_template.get_component_map().get("endpoint")

        # Keep track of generated code for dependencies
        generated_code = {
            "endpoint_code": primary_component.get("generated_code", ""),
            "controller_code": primary_component.get("generated_code", ""),
            "model_code": None,
        }

        # Generate each required component
        for component_type in required_components:
            # Skip the primary component as we've already generated it
            if component_type == endpoint_component:
                continue

            await self._notify_info(f"Generating {component_type} for {entity_name}")

            # Generate the component
            component_result = await self._generate_component(
                language_template,
                component_type,
                project_id,
                entity_name,
                prompt,
                **generated_code,
                method=method,
                endpoint_path=endpoint_path,
            )

            # Store the result
            result[component_type] = component_result

            # Store generated code for dependencies
            if component_type == language_template.get_component_map().get("model"):
                generated_code["model_code"] = component_result.get(
                    "generated_code", ""
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

    async def _check_and_update_existing_model(
        self, project_id, entity_name, prompt_description, endpoint_code, language
    ):
        """
        Check if entity already exists and update it if needed based on the new endpoint.

        This method analyzes the requested endpoint functionality against an existing model
        to determine if modifications are needed. If changes are required, it generates
        updates to the model and related schema, and may create a migration.

        Args:
            project_id: Identifier for the project being modified
            entity_name: Name of the entity to check and potentially update
            prompt_description: Natural language description of the desired functionality
            endpoint_code: Generated code for the endpoint/controller
            language: Target programming language

        Returns:
            Dict or None: Update results if updates were made, None if no updates needed
                or if the model doesn't exist

        Raises:
            Exception: Errors during model updating are caught and logged
        """
        try:
            # Verify the model exists
            existing_model = await self._check_for_existing_model(
                project_id, entity_name
            )
            if not existing_model:
                return None

            logger.info(
                f"Found existing model for entity {entity_name}, analyzing potential updates"
            )

            # Process model changes
            update_result = await ModelSchemaManager.process_model_changes(
                project_id=project_id,
                entity_name=entity_name,
                prompt_description=prompt_description,
                endpoint_code=endpoint_code,
                generate_migration=False,  # Don't generate migration automatically
                language=language,
            )

            # Generate migration if model was updated
            if update_result and update_result.get("model_updated", False):
                logger.info("Model was updated, generating migration")

                # Get language template
                language_template = LanguageTemplateFactory.get_template(language)
                component_map = language_template.get_component_map()

                # Check if this language supports migrations
                migration_component = component_map.get("migration")
                if migration_component:
                    migration_result = await self._generate_component(
                        language_template=language_template,
                        component_type=migration_component,
                        project_id=project_id,
                        entity_name=entity_name,
                        entity_description=prompt_description,
                        model_code=update_result.get("content_base64", None),
                    )

                    # Add migration to files to commit
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

            return update_result
        except Exception as e:
            logger.error(f"Error checking for existing model: {str(e)}", exc_info=True)
            return None

    async def _commit_updated_files(self, project_id, files_to_commit):
        """
        Commit updated files to Git repository individually.

        This method handles committing multiple files to Git with individual commit
        messages, typically used when updating existing models and related components.

        Args:
            project_id: Identifier for the project repository
            files_to_commit: List of dictionaries containing file paths, content, and commit messages

        Returns:
            Dict: Results of commit operations by file path

        Raises:
            Exception: Errors during Git operations are caught and logged
        """

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

    async def _commit_files_to_git(
        self, project_id, generation_result, language, language_template
    ):
        """
        Commit all generated files to Git repository following language-specific commit strategy.

        This method handles committing all generated components to Git following a
        language-specific commit strategy that defines the order and commit messages.
        It attempts to use the language template's commit strategy first, and falls back
        to a legacy approach if that fails.

        Args:
            project_id: Identifier for the project repository
            generation_result: Dictionary containing all generated components
            language: Target programming language
            language_template: Template for the target programming language

        Returns:
            Dict: Results of commit operations by component type

        Raises:
            Exception: Errors in commit strategy are caught and handled by falling back
                to the legacy commit method
        """
        try:
            # Get commit strategy from language template
            commit_strategy = language_template.get_commit_strategy()
            commit_order = commit_strategy.get("commit_order", [])
            commit_messages = commit_strategy.get("commit_messages", {})

            # Get entity name for commit messages
            entity_name = generation_result.get("entity_name", "Entity")

            # Initialize results
            git_results = {}

            # Commit files in the specified order
            for component in commit_order:
                component_data = generation_result.get(component)

                # Skip if component doesn't exist
                if not component_data:
                    continue

                try:
                    # Format commit message
                    message_template = commit_messages.get(
                        component, f"Add {component} for {entity_name}"
                    )

                    # Replace placeholders in message
                    commit_message = message_template.format(
                        entity_name=entity_name,
                        method=component_data.get("method", "GET"),
                        endpoint_path=component_data.get("endpoint_path", ""),
                    )

                    # Commit the file
                    commit_result = await GitService.commit_file_update(
                        project_id=project_id,
                        new_code=component_data.get("generated_code", ""),
                        file_path=component_data.get("file_path", ""),
                        commit_message=commit_message,
                    )

                    git_results[component] = commit_result
                    logger.info(
                        f"Committed {component} file: {component_data.get('file_path')}"
                    )

                except Exception as e:
                    logger.error(f"Failed to commit {component}: {e}")

            return git_results
        except Exception as e:
            logger.error(f"Error in commit strategy: {str(e)}", exc_info=True)
            return await self._legacy_commit_files_to_git(project_id, generation_result)

    async def _legacy_commit_files_to_git(self, project_id, generation_result):
        """
        Legacy method for committing files to Git (fallback strategy).

        This method provides a fallback approach for committing generated files
        when the language-specific commit strategy fails. It uses a predefined
        component order and generic commit messages.

        Args:
            project_id: Identifier for the project repository
            generation_result: Dictionary containing all generated components

        Returns:
            Dict: Results of commit operations by component type
        """
        git_results = {}

        # Handle endpoints/controllers
        try:
            endpoint = generation_result.get("endpoint", {}) or generation_result.get(
                "controller", {}
            )
            if endpoint:
                endpoint_commit = await GitService.commit_file_update(
                    project_id=project_id,
                    new_code=endpoint.get("generated_code", ""),
                    file_path=endpoint.get("file_path", ""),
                    commit_message=f"Add {endpoint.get('method', 'GET')} endpoint for {endpoint.get('endpoint_path', '')}",
                )
                git_results["endpoint"] = endpoint_commit
        except Exception as e:
            logger.error(f"Failed to commit endpoint: {e}")

        # Handle models and related components
        model = generation_result.get("model")
        if model and not model.get("exists", False):
            try:
                # Commit model
                model_commit = await GitService.commit_file_update(
                    project_id=project_id,
                    new_code=model.get("generated_code", ""),
                    file_path=model.get("file_path", ""),
                    commit_message=f"Add {model.get('entity_name', 'Entity')} model",
                )
                git_results["model"] = model_commit

                # Commit schema/validation
                schema = generation_result.get("schema", {}) or generation_result.get(
                    "validation", {}
                )
                if schema:
                    schema_commit = await GitService.commit_file_update(
                        project_id=project_id,
                        new_code=schema.get("generated_code", ""),
                        file_path=schema.get("file_path", ""),
                        commit_message=f"Add {schema.get('entity_name', 'Entity')} schema",
                    )
                    git_results["schema"] = schema_commit

                # Commit migration if exists
                migration = generation_result.get("migration", {})
                if migration and migration.get("generated_code"):
                    migration_commit = await GitService.commit_file_update(
                        project_id=project_id,
                        new_code=migration.get("generated_code", ""),
                        file_path=migration.get("file_path", ""),
                        commit_message=f"Add migration for {migration.get('entity_name', 'Entity')} model",
                    )
                    git_results["migration"] = migration_commit
            except Exception as e:
                logger.error(f"Failed to commit model/schema/migration: {e}")

        # Handle helpers/utils
        try:
            helpers = generation_result.get("helpers", {}) or generation_result.get(
                "utils", {}
            )
            if helpers:
                helpers_commit = await GitService.commit_file_update(
                    project_id=project_id,
                    new_code=helpers.get("generated_code", ""),
                    file_path=helpers.get("file_path", ""),
                    commit_message=f"Add helper functions for {helpers.get('entity_name', 'Entity')}",
                )
                git_results["helpers"] = helpers_commit
        except Exception as e:
            logger.error(f"Failed to commit helpers: {e}")

        # Handle routes (JavaScript specific)
        try:
            route = generation_result.get("route", {})
            if route:
                route_commit = await GitService.commit_file_update(
                    project_id=project_id,
                    new_code=route.get("generated_code", ""),
                    file_path=route.get("file_path", ""),
                    commit_message=f"Add routes for {route.get('entity_name', 'Entity')} API",
                )
                git_results["route"] = route_commit
        except Exception as e:
            logger.error(f"Failed to commit route: {e}")

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
