import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from app.api.v1.schemas.code_generation import (
    CodeGenerationRequest,
    CodeGenerationResponse,
    GenerationResult,
)
from app.api.v1.services.git_service import GitService
from app.api.v1.services.language_templates import LanguageTemplateFactory
from app.api.v1.services.llm_service import LLMService
from app.api.v1.services.project_analysis_service import ProjectAnalysisService
from app.api.v1.services.model_schema_update_service import ModelSchemaManager

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
            "validation": self.on_schema_start,    # Map JS validation to schema
            "helpers": self.on_helpers_start,
            "utils": self.on_helpers_start,        # Map JS utils to helpers
            "migration": self.on_migration_start,
            "route": self.on_endpoint_start,       # Map JS routes to endpoint
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

    async def generate_code(self, request: CodeGenerationRequest) -> CodeGenerationResponse:
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
            endpoint_path = request.endpoint_path or f"/api/{prompt.lower().replace(' ', '-')}"
            
            # Initialize language template
            language_template = LanguageTemplateFactory.get_template(language)
            
            # Log generation start
            logger.info(f"Generating code in {language} for: {prompt}")
            await self._notify_info(f"Starting code generation in {language} for: {prompt}")
            
            # Step 1: Generate primary endpoint/controller
            primary_component = await self._generate_primary_component(
                language_template, project_id, prompt, method, endpoint_path, 
                request.additional_context
            )
            
            # Step 2: Determine if database components are needed
            needs_database = language_template.needs_database(primary_component.get("generated_code", ""))
            
            # Step 3: Extract entity name
            entity_name = self._extract_entity_name(language_template, primary_component)
            primary_component["entity_name"] = entity_name
            
            # Update file path with correct entity name
            component_type = language_template.get_component_map().get("endpoint")
            primary_component["file_path"] = language_template.get_component_paths(
                project_id, entity_name
            )[component_type]
            
            # Step 4: Initialize result dictionary
            result = self._initialize_result_dictionary(
                primary_component, language_template, entity_name, needs_database, component_type
            )
            
            # Step 5: Generate database components if needed
            if needs_database:
                await self._notify_info(f"Database components needed: {needs_database}")
                
                # Check for existing models
                existing_model = await self._check_for_existing_model(project_id, entity_name)
                
                if existing_model:
                    # Handle model updates
                    await self._handle_existing_model(
                        result, project_id, entity_name, prompt, primary_component, language, 
                        language_template
                    )
                else:
                    # Generate new components
                    await self._generate_new_components(
                        result, language_template, project_id, entity_name, prompt, 
                        primary_component, method, endpoint_path
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
                result=GenerationResult(**result)
            )
            
        except Exception as e:
            error_msg = f"Error in code generation: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await self._notify_info(error_msg)
            
            return CodeGenerationResponse(
                success=False,
                message=error_msg,
                result=None
            )

    async def _generate_primary_component(
        self, language_template, project_id, prompt, method, endpoint_path, additional_context
    ):
        """Generate the primary component (endpoint/controller)"""
        # Get the endpoint component type for this language
        endpoint_component = language_template.get_component_map().get("endpoint")
        if not endpoint_component:
            raise ValueError(f"Language does not support endpoints/controllers")
            
        # Generate the component
        return await self._generate_component(
            language_template,
            endpoint_component,
            project_id,
            "temp",  # Temporary entity name, will be replaced
            prompt,
            method=method,
            endpoint_path=endpoint_path,
            additional_context=additional_context
        )
        
    def _extract_entity_name(self, language_template, primary_component):
        """Extract entity name from the generated code"""
        extracted_name = language_template.extract_entity_from_code(
            primary_component.get("generated_code", "")
        )
        return extracted_name or "User"  # Default to "User" if not found
        
    def _initialize_result_dictionary(
        self, primary_component, language_template, entity_name, needs_database, component_type
    ):
        """Initialize the result dictionary with common fields"""
        return {
            component_type: primary_component,
            "language": language_template.get_file_extension(),
            "file_extension": language_template.get_file_extension(),
            "entity_name": entity_name,
            "detected_database_usage": needs_database
        }
        
    async def _handle_existing_model(
        self, result, project_id, entity_name, prompt, primary_component, language, language_template
    ):
        """Handle updates to an existing model"""
        await self._notify_info(f"Found existing model for {entity_name}, checking for updates...")
        
        # Process potential model updates
        update_result = await self._check_and_update_existing_model(
            project_id=project_id,
            entity_name=entity_name,
            prompt_description=prompt,
            endpoint_code=primary_component.get("generated_code", ""),
            language=language
        )
        
        if update_result and update_result.get("model_updated", False):
            # Model was updated
            await self._notify_info(f"Updated existing model {entity_name}")
            await self._process_model_updates(result, update_result, entity_name, project_id)
        else:
            await self._notify_info(f"No updates needed for existing model {entity_name}")
            
    async def _process_model_updates(self, result, update_result, entity_name, project_id):
        """Process model updates and add to result"""
        # Add model update details
        result["model"] = {
            "exists": True,
            "updated": True,
            "entity_name": entity_name,
            "file_path": update_result.get("model_file"),
            "generated_code": update_result.get("content_base64"),
            "update_details": update_result.get("field_changes"),
        }
        
        # Add schema updates if applicable
        if update_result.get("schema_updated", False):
            result["schema"] = {
                "exists": True,
                "updated": True,
                "entity_name": entity_name,
                "schema_details": update_result.get("schema_results", []),
            }
        
        # Add migration if generated
        if update_result.get("migration"):
            result["migration"] = update_result.get("migration")
        
        # Commit updated files
        if update_result.get("files_to_commit"):
            await self._commit_updated_files(project_id, update_result.get("files_to_commit"))
            
    async def _generate_new_components(
        self, result, language_template, project_id, entity_name, prompt, 
        primary_component, method, endpoint_path
    ):
        """Generate new components for an entity"""
        await self._notify_info(f"Generating new components for {entity_name}")
        
        # Get required components for this language
        required_components = language_template.get_required_components()
        endpoint_component = language_template.get_component_map().get("endpoint")
        
        # Keep track of generated code for dependencies
        generated_code = {
            "endpoint_code": primary_component.get("generated_code", ""),
            "controller_code": primary_component.get("generated_code", ""),
            "model_code": None
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
                endpoint_path=endpoint_path
            )
            
            # Store the result
            result[component_type] = component_result
            
            # Store generated code for dependencies
            if component_type == language_template.get_component_map().get("model"):
                generated_code["model_code"] = component_result.get("generated_code", "")
                
    async def _generate_component(
        self, language_template, component_type, project_id, entity_name, 
        entity_description, **kwargs
    ):
        """Generate a specific component using the language template"""
        try:
            # Notify component generation start
            await self._notify_event("start", component_type, {
                "entity_name": entity_name,
                "component_type": component_type
            })
            
            # Generate the component
            result = await language_template.generate_component(
                component_type=component_type,
                project_id=project_id,
                entity_name=entity_name,
                entity_description=entity_description,
                **kwargs
            )
            
            # Notify component generation complete
            await self._notify_event("complete", component_type, result)
            
            return result
        except Exception as e:
            logger.error(f"Error generating {component_type}: {str(e)}", exc_info=True)
            raise
            
    async def _check_for_existing_model(self, project_id, entity_name):
        """Check if an entity already exists in the project"""
        try:
            # Analyze project to find existing models
            project_analysis = await ProjectAnalysisService.analyze_project(project_id)
            
            # Find matching model
            return LLMService._find_existing_model(entity_name, project_analysis.get("models", []))
        except Exception as e:
            logger.error(f"Error checking for existing model: {str(e)}", exc_info=True)
            return None
            
    async def _check_and_update_existing_model(
        self, project_id, entity_name, prompt_description, endpoint_code, language
    ):
        """Check if entity already exists and update it if needed"""
        try:
            # Verify the model exists
            existing_model = await self._check_for_existing_model(project_id, entity_name)
            if not existing_model:
                return None
                
            logger.info(f"Found existing model for entity {entity_name}, analyzing potential updates")
            
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
                        model_code=update_result.get("content_base64", None)
                    )
                    
                    # Add migration to files to commit
                    if migration_result and "generated_code" in migration_result:
                        logger.info(f"Adding migration to commit: {migration_result.get('file_path')}")
                        
                        if "files_to_commit" not in update_result:
                            update_result["files_to_commit"] = []
                            
                        update_result["files_to_commit"].append({
                            "file_path": migration_result.get("file_path"),
                            "commit_message": f"feat: Add migration for {entity_name} model changes",
                            "content": migration_result.get("generated_code"),
                        })
                        
                        update_result["migration"] = migration_result
            
            return update_result
        except Exception as e:
            logger.error(f"Error checking for existing model: {str(e)}", exc_info=True)
            return None
            
    async def _commit_updated_files(self, project_id, files_to_commit):
        """Commit updated files to Git repository"""
        commit_results = {}
        
        try:
            for file_info in files_to_commit:
                file_path = file_info.get("file_path")
                content = file_info.get("content")
                commit_message = file_info.get("commit_message")
                
                if not file_path or not content:
                    logger.warning(f"Skipping commit for file with missing path or content: {file_path}")
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
        """Commit all generated files to Git repository"""
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
                    message_template = commit_messages.get(component, f"Add {component} for {entity_name}")
                    
                    # Replace placeholders in message
                    commit_message = message_template.format(
                        entity_name=entity_name,
                        method=component_data.get('method', 'GET'),
                        endpoint_path=component_data.get('endpoint_path', ''),
                    )
                    
                    # Commit the file
                    commit_result = await GitService.commit_file_update(
                        project_id=project_id,
                        new_code=component_data.get("generated_code", ""),
                        file_path=component_data.get("file_path", ""),
                        commit_message=commit_message,
                    )
                    
                    git_results[component] = commit_result
                    logger.info(f"Committed {component} file: {component_data.get('file_path')}")
                    
                except Exception as e:
                    logger.error(f"Failed to commit {component}: {e}")
            
            return git_results
        except Exception as e:
            logger.error(f"Error in commit strategy: {str(e)}", exc_info=True)
            return await self._legacy_commit_files_to_git(project_id, generation_result)
            
    async def _legacy_commit_files_to_git(self, project_id, generation_result):
        """Legacy method for committing files to Git (fallback)"""
        git_results = {}
        
        # Handle endpoints/controllers
        try:
            endpoint = generation_result.get("endpoint", {}) or generation_result.get("controller", {})
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
                schema = generation_result.get("schema", {}) or generation_result.get("validation", {})
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
            helpers = generation_result.get("helpers", {}) or generation_result.get("utils", {})
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
        """Notify event callbacks for a component event"""
        callback_dict = self.on_component_start if event_type == "start" else self.on_component_complete
        
        # Try specific component callback
        callback = callback_dict.get(component_type)
        if callback:
            try:
                await callback(component_type, data)
            except Exception as e:
                logger.error(f"Error in {event_type} callback for {component_type}: {str(e)}")
        
        # Try generic callback
        generic_callback = callback_dict.get("*")
        if generic_callback:
            try:
                await generic_callback(component_type, data)
            except Exception as e:
                logger.error(f"Error in generic {event_type} callback: {str(e)}")
    
    async def _notify_info(self, message):
        """Send an info message through the callback if available"""
        if self.on_info:
            try:
                await self.on_info(message)
            except Exception as e:
                logger.error(f"Error in info callback: {str(e)}")