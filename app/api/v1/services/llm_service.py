import logging
import ast
from typing import Dict, Any, Optional, List, Set
from pathlib import Path
from app.api.v1.services.langchain_service import LangchainService
from app.api.v1.utils.prompt_manager import PromptManager
from app.api.v1.utils.code_analysis import DependencyVisitor
from app.api.db.database import get_db
from app.api.v1.schemas.code_generation import CodeGenerationRequest
from app.api.v1.services.project_analysis_service import ProjectAnalysisService
from config import settings

logger = logging.getLogger(__name__)

class LLMService:
    """
    Service for generating code artifacts in a step-by-step approach.
    Updated to use Langchain for improved generation.
    """
    
    @staticmethod
    async def generate_complete_endpoint(
        project_id: str,
        endpoint_description: str,
        method: Optional[str] = None,
        endpoint_path: Optional[str] = None,
        additional_context: Optional[str] = None,
        language: str = "python"
    ) -> Dict[str, Any]:
        """
        Generate complete endpoint with models, schemas, and migrations using a step-by-step approach
        
        Args:
            project_id: The project identifier
            endpoint_description: User's description of the endpoint
            method: Optional HTTP method (GET, POST, etc.)
            endpoint_path: Optional path for the endpoint
            additional_context: Optional additional context
            language: Programming language to generate code in (python, javascript, etc.)
            
        Returns:
            Dictionary containing all generated artifacts
        """
        # Default values if not provided
        method_to_use = method.upper() if method else "POST"
        path_to_use = endpoint_path or f"api/v1/{endpoint_description.lower().replace(' ', '_')}"
        
        try:
            # Step 1: Generate the endpoint and identify entity (using Langchain)
            logger.info(f"Step 1: Generating {language} endpoint for: {endpoint_description}")
            endpoint_result = await LangchainService.generate_endpoint(
                project_id=project_id,
                endpoint_description=endpoint_description,
                method=method_to_use,
                endpoint_path=path_to_use,
                language=language,
                additional_context=additional_context
            )
            
            # --- Perform AST Analysis on endpoint code ---
            dependencies_v1: Dict[str, Set[str]] = {}
            primary_entity_ast_v1: Optional[str] = None
            try:
                logger.info(f"Performing AST analysis on {language} endpoint code...")
                if language == "python":
                    tree_v1 = ast.parse(endpoint_result["generated_code"])
                    visitor_v1 = DependencyVisitor()
                    visitor_v1.visit(tree_v1)
                    dependencies_v1, primary_entity_ast_v1 = visitor_v1.get_analysis_results()
                    logger.info(f"AST Analysis Results - Primary Entity Guess: {primary_entity_ast_v1}")
                    logger.info(f"AST Analysis Results - Dependencies: {dependencies_v1}")
                else:
                    # For non-Python languages, use alternative entity extraction
                    # This could be a simpler regex-based approach or a language-specific parser
                    from app.api.v1.utils.entity_extractor import extract_entity_from_code
                    primary_entity_ast_v1 = extract_entity_from_code(endpoint_result["generated_code"], language)
                    logger.info(f"Entity extraction result for {language}: {primary_entity_ast_v1}")
            except SyntaxError as e:
                logger.error(f"AST Parsing failed for generated {language} code: {e}. Cannot perform dependency analysis.")
            except Exception as e:
                logger.error(f"Unexpected error during {language} code analysis: {e}", exc_info=True)
            # --- End AST Analysis ---

            # Determine the entity name using AST result, fallback to "User"
            entity_name = None
            if primary_entity_ast_v1:
                entity_name = primary_entity_ast_v1
                logger.info(f"Using entity name from code analysis: '{entity_name}'")
            else:
                entity_name = "User" # Default fallback
                logger.warning(f"Code analysis failed or yielded no entity name. Using final fallback: '{entity_name}'")

            # Ensure entity_name is assigned
            if not entity_name:
                 logger.error("CRITICAL: Entity name determination failed completely. Defaulting to 'User'.")
                 entity_name = "User"
            
            # Check if entity already exists in project
            project_analysis = await ProjectAnalysisService.analyze_project(project_id)
            existing_model = LLMService._find_existing_model(entity_name, project_analysis.get("models", []))

            # If model exists, check if it needs updates
            if existing_model:
                logger.info(f"Found existing model for entity: {entity_name}")
                
                # Check if model needs updates based on endpoint description
                logger.info(f"Checking if existing model needs updates for: {entity_name}")
                update_result = await LLMService.update_existing_model_for_endpoint(
                    project_id=project_id,
                    endpoint_description=endpoint_description,
                    entity_name=entity_name,
                    endpoint_code=endpoint_result["generated_code"],
                    language=language
                )
                
                if update_result.get("model_updated", False):
                    # Model was updated with new fields
                    logger.info(f"Updated existing model {entity_name} with new fields: {update_result.get('fields_added', [])}")
                    return {
                        "endpoint": endpoint_result,
                        "model": {
                            "exists": True, 
                            "name": entity_name, 
                            "updated": True, 
                            "fields_added": update_result.get("fields_added", [])
                        },
                        "schema": {
                            "exists": True, 
                            "name": entity_name, 
                            "updated": update_result.get("schema_updated", False)
                        },
                        "migration": {
                            "exists": True, 
                            "generated": update_result.get("migration") is not None
                        },
                        "update_details": update_result,
                        "language": language
                    }
                else:
                    # Model exists but no updates were needed
                    logger.info(f"Using existing model for entity: {entity_name} (no updates needed)")
                    return {
                        "endpoint": endpoint_result,
                        "model": {"exists": True, "name": entity_name},
                        "schema": {"exists": True, "name": entity_name},
                        "migration": {"exists": True},
                        "language": language
                    }

            
            # Step 2: Generate the model using Langchain
            logger.info(f"Step 2: Generating {language} model for entity: {entity_name}")
            model_result = await LangchainService.generate_model(
                project_id=project_id,
                entity_name=entity_name,
                entity_description=endpoint_description,
                language=language,
                endpoint_code=endpoint_result["generated_code"]
            )
            
            # Step 3: Generate the schema using Langchain
            logger.info(f"Step 3: Generating {language} schema for entity: {entity_name}")
            schema_result = await LangchainService.generate_schema(
                project_id=project_id,
                entity_name=entity_name,
                language=language,
                endpoint_code=endpoint_result["generated_code"],
                model_code=model_result["generated_code"]
            )
            
            # Step 4: Generate the migration using Langchain
            logger.info(f"Step 4: Generating {language} migration for entity: {entity_name}")
            migration_result = await LangchainService.generate_migration(
                project_id=project_id,
                entity_name=entity_name,
                language=language,
                model_code=model_result["generated_code"]
            )
            
            # Step 5: Generate helper functions using Langchain
            logger.info(f"Step 5: Generating {language} helper functions for entity: {entity_name}")
            helpers_result = await LangchainService.generate_helpers(
                project_id=project_id,
                entity_name=entity_name,
                entity_description=endpoint_description,
                language=language,
                endpoint_code=endpoint_result["generated_code"],
                model_code=model_result["generated_code"],
                schema_code=schema_result["generated_code"]
            )
            
            return {
                "endpoint": endpoint_result,
                "model": model_result,
                "schema": schema_result,
                "migration": migration_result,
                "helpers": helpers_result,
                "language": language
            }
            
        except Exception as e:
            logger.error(f"Error in step-by-step generation: {str(e)}", exc_info=True)
            raise Exception(f"Failed to generate complete endpoint: {str(e)}")
    
    @staticmethod
    async def generate_endpoint_only(
        project_id: str,
        endpoint_description: str,
        method: str,
        endpoint_path: str,
        additional_context: Optional[str] = None,
        language: str = "python"
    ) -> Dict[str, Any]:
        """
        Generates an API endpoint implementation based on the provided parameters.
        Updated to use Langchain.

        Args:
            project_id: The ID of the project for which the endpoint is being generated.
            endpoint_description: A brief description of the endpoint's functionality.
            method: The HTTP method to be used (e.g., GET, POST, PUT, DELETE).
            endpoint_path: The URL path of the endpoint.
            additional_context: Any additional details or constraints to consider.
            language: Programming language to generate code in (python, javascript, etc.)

        Returns:
            Dict[str, Any]: Information about the generated endpoint.
        """
        try:
            # Use Langchain service for generation
            return await LangchainService.generate_endpoint(
                project_id=project_id,
                endpoint_description=endpoint_description,
                method=method,
                endpoint_path=endpoint_path,
                language=language,
                additional_context=additional_context
            )
        except Exception as e:
            logger.error(f"Error generating endpoint: {str(e)}", exc_info=True)
            raise Exception(f"Failed to generate endpoint: {str(e)}")
    
    @staticmethod
    async def generate_model(
        project_id: str,
        entity_name: str,
        entity_description: str,
        endpoint_code: Optional[str] = None,
        language: str = "python"
    ) -> Dict[str, Any]:
        """
        Generates a model for a given entity.
        Updated to use Langchain.

        Args:
            project_id: The unique identifier of the project.
            entity_name: The name of the entity for which the model is generated.
            entity_description: A brief description of the entity.
            endpoint_code: Optional endpoint code for context.
            language: Programming language to generate code in (python, javascript, etc.)

        Returns:
            Dict[str, Any]: Information about the generated model.
        """
        try:
            # Use Langchain service for generation
            return await LangchainService.generate_model(
                project_id=project_id,
                entity_name=entity_name,
                entity_description=entity_description,
                language=language,
                endpoint_code=endpoint_code
            )
        except Exception as e:
            logger.error(f"Error generating model: {str(e)}", exc_info=True)
            raise Exception(f"Failed to generate model: {str(e)}")
    
    @staticmethod
    async def generate_schema(
        project_id: str,
        entity_name: str,
        endpoint_code: Optional[str] = None,
        model_code: Optional[str] = None,
        language: str = "python"
    ) -> Dict[str, Any]:
        """
        Generates a schema for a given entity.
        Updated to use Langchain.

        Args:
            project_id: The unique identifier of the project.
            entity_name: The name of the entity for which the schema is generated.
            endpoint_code: Optional endpoint code for context.
            model_code: Optional model code for context.
            language: Programming language to generate code in (python, javascript, etc.)

        Returns:
            Dict[str, Any]: Information about the generated schema.
        """
        try:
            # Use Langchain service for generation
            return await LangchainService.generate_schema(
                project_id=project_id,
                entity_name=entity_name,
                language=language,
                endpoint_code=endpoint_code,
                model_code=model_code
            )
        except Exception as e:
            logger.error(f"Error generating schema: {str(e)}", exc_info=True)
            raise Exception(f"Failed to generate schema: {str(e)}")
    
    @staticmethod
    async def generate_migration(
        project_id: str,
        entity_name: str,
        model_code: Optional[str] = None,
        language: str = "python"
    ) -> Dict[str, Any]:
        """
        Generates a migration for a given entity.
        Updated to use Langchain.

        Args:
            project_id: The unique identifier of the project.
            entity_name: The name of the entity for which the migration is generated.
            model_code: Optional model code for context.
            language: Programming language to generate code in (python, javascript, etc.)

        Returns:
            Dict[str, Any]: Information about the generated migration.
        """
        try:
            # Use Langchain service for generation
            return await LangchainService.generate_migration(
                project_id=project_id,
                entity_name=entity_name,
                language=language,
                model_code=model_code
            )
        except Exception as e:
            logger.error(f"Error generating migration: {str(e)}", exc_info=True)
            raise Exception(f"Failed to generate migration: {str(e)}")
    
    @staticmethod
    async def generate_helpers(
        project_id: str,
        entity_name: str,
        entity_description: str,
        entity_fields: Optional[str] = None,
        endpoint_code: Optional[str] = None,
        model_code: Optional[str] = None,
        schema_code: Optional[str] = None,
        language: str = "python"
    ) -> Dict[str, Any]:
        """
        Generates helper functions for a given entity.
        Updated to use Langchain.

        Args:
            project_id: The unique identifier of the project.
            entity_name: The name of the entity for which helper functions are generated.
            entity_description: A brief description of the entity.
            entity_fields: Optional fields associated with the entity.
            endpoint_code: Optional endpoint code for context.
            model_code: Optional model code for context.
            schema_code: Optional schema code for context.
            language: Programming language to generate code in (python, javascript, etc.)

        Returns:
            Dict[str, Any]: Information about the generated helpers.
        """
        try:
            # Use Langchain service for generation
            return await LangchainService.generate_helpers(
                project_id=project_id,
                entity_name=entity_name,
                entity_description=entity_description,
                language=language,
                endpoint_code=endpoint_code,
                model_code=model_code,
                schema_code=schema_code
            )
        except Exception as e:
            logger.error(f"Error generating helper functions: {str(e)}", exc_info=True)
            raise Exception(f"Failed to generate helper functions: {str(e)}")
    
    @staticmethod
    async def update_existing_model_for_endpoint(
        project_id: str,
        endpoint_description: str,
        entity_name: str,
        endpoint_code: str,
        language: str = "python"
    ) -> Dict[str, Any]:
        """
        Update an existing model with new fields required for an endpoint
        
        Args:
            project_id: The project identifier
            endpoint_description: Description of the endpoint being created
            entity_name: Entity name to update
            endpoint_code: The generated endpoint code
            language: Programming language of the code
            
        Returns:
            Dictionary containing update results
        """
        try:
            # This function might need to be updated to use Langchain or remain as-is
            # For now, we'll keep the original implementation
            from app.api.v1.services.model_schema_update_service import ModelSchemaManager
            
            update_result = await ModelSchemaManager.process_model_changes(
                project_id=project_id,
                entity_name=entity_name,
                prompt_description=endpoint_description,
                endpoint_code=endpoint_code,
                generate_migration=True,
                language=language
            )

            return update_result
            
        except Exception as e:
            logger.error(f"Error updating model for endpoint: {str(e)}", exc_info=True)
            return {
                "model_updated": False,
                "error": str(e)
            }
    
    # Keep required helper methods
    @staticmethod
    def _find_existing_model(entity_name: str, models: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Check if a model with the given entity name already exists"""
        if not entity_name or not models:
            logger.info(f"No entity name provided or no models available to search")
            return None

        entity_lower = entity_name.lower()
        logger.info(f"Looking for model matching entity: '{entity_name}' (lowercase: '{entity_lower}')")
        
        # Generate variations of the entity name for flexible matching
        entity_variations = [
            entity_lower,                
            entity_lower + "s",          
            entity_lower.rstrip('s'),    
            entity_lower + "model",      
            entity_lower.replace("_", "") 
        ]
        
        logger.info(f"Checking variations: {entity_variations}")
        logger.info(f"Available models: {[m.get('name', '') for m in models]}")
        
        for model in models:
            model_name = model.get("name", "").lower()
            logger.info(f"Comparing with model: '{model.get('name')}' (lowercase: '{model_name}')")
            
            # Check for direct match
            if model_name == entity_lower:
                logger.info(f"✅ MATCH FOUND: Exact match with model '{model.get('name')}'")
                return model
                
            # Check variations
            if model_name in entity_variations or any(var == model_name for var in entity_variations):
                logger.info(f"✅ MATCH FOUND: Variation match with model '{model.get('name')}'")
                return model
                
            # Check if entity name is contained in model name or vice versa
            if entity_lower in model_name or model_name in entity_lower:
                logger.info(f"✅ MATCH FOUND: Substring match with model '{model.get('name')}'")
                return model
        
        logger.warning(f"❌ NO MATCH FOUND: No model found matching entity '{entity_name}'")
        return None
    
    # Define a backup clean_code method in case it's needed
    @staticmethod
    def clean_code(code_text: str) -> str:
        """Remove markdown code block formatting from the provided code text."""
        # Use strip() to remove leading/trailing whitespace
        code_text = code_text.strip()
        
        # Check if code is enclosed in markdown code blocks
        if code_text.startswith("```"):
            # Split into lines and remove the first and last line if they are markdown markers
            lines = code_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            return "\n".join(lines).strip()
        return code_text
    
    # Define a backup generate_file_hash method in case it's needed
    @staticmethod
    def generate_file_hash(code: str) -> str:
        """Generates an MD5 hash from code content"""
        import hashlib
        return hashlib.md5(code.encode('utf-8')).hexdigest()
    
    @staticmethod
    def needs_model_and_schema(endpoint_code: str) -> bool:
        """
        Determines if the endpoint requires database models, schemas and migrations.
        
        Args:
            endpoint_code: The generated endpoint code to analyze
            
        Returns:
            True if models/schemas are needed, False otherwise
        """
        # Strong indicators this endpoint DOES need database interaction
        db_related_patterns = [
            # Database session imports and dependencies
            r'from\s+core\.database\s+import\s+get_db',
            r'db\s*:\s*Session\s*=\s*Depends\(get_db\)',
            r'const\s+.*\s+=\s+require\([\'"].*database[\'"].*\)',
            r'const\s+.*\s+=\s+require\([\'"]mongoose[\'"].*\)',
            r'const\s+.*\s+=\s+require\([\'"]sequelize[\'"].*\)',
            
            # Database query operations
            r'db\.query',
            r'db\.add',
            r'db\.commit',
            r'db\.refresh',
            r'findOne',
            r'findById',
            r'findAll',
            r'create',
            r'update',
            r'destroy',
            r'save\(',
            
            # ORM-related operations
            r'\.filter\(',
            r'\.all\(\)',
            r'\.first\(\)',
            r'\.update\(',
            r'\.delete\(',
            r'Model\.',
            r'\.findAndCountAll',
        ]
        
        # First check if any database-related pattern is present
        import re
        for pattern in db_related_patterns:
            if re.search(pattern, endpoint_code):
                return True
        
        # Common health check and status endpoint patterns that DON'T need DB
        health_check_patterns = [
            r'return\s*{\s*["\']status["\']\s*:\s*["\']OK["\']\s*}',
            r'return\s*{\s*["\']status["\']\s*:\s*["\']ok["\']\s*}',
            r'health_check',
            r'/api/health',
            r'/health',
            r'status\.HTTP_200_OK',
            r'res\.status\(200\)\.json\(\{[\s\n]*["\']status["\']\s*:\s*["\']ok[\'"]',
        ]
        
        # If multiple health check patterns match, it's likely a simple health endpoint
        health_pattern_matches = 0
        for pattern in health_check_patterns:
            if re.search(pattern, endpoint_code):
                health_pattern_matches += 1
        
        if health_pattern_matches >= 2:  # If at least two health check patterns match
            return False
        
        # Check for model imports across different languages
        model_import_patterns = [
            # Python patterns
            r'from\s+models\.',
            r'import\s+models\.',
            # JavaScript patterns
            r'require\([\'"]\.\.?\/models',
            r'import.*from.*[\'"]\.\.?\/models',
        ]
        
        for pattern in model_import_patterns:
            if re.search(pattern, endpoint_code):
                return True
        
        # Check for schema/validation imports
        schema_import_patterns = [
            # Python patterns
            r'from\s+schemas\.',
            r'import\s+schemas\.',
            # JavaScript patterns
            r'require\([\'"]\.\.?\/schemas',
            r'import.*from.*[\'"]\.\.?\/schemas',
            r'require\([\'"]joi[\'"]',
            r'import.*from.*[\'"]joi[\'"]',
            r'express-validator',
        ]
        
        for pattern in schema_import_patterns:
            if re.search(pattern, endpoint_code):
                return True
        
        # Look for body parsing and request validation which often indicates model needs
        validation_patterns = [
            r'req\.body',
            r'request\.json',
            r'body\(',
            r'validate',
            r'validator',
            r'@Body\(',
        ]
        
        validation_matches = 0
        for pattern in validation_patterns:
            if re.search(pattern, endpoint_code):
                validation_matches += 1
        
        # If multiple validation patterns match, likely needs models
        if validation_matches >= 2:
            return True
        
        # Make the default behavior conservative - don't generate models
        # unless we have strong indicators that they're needed
        return False