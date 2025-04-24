import base64
import datetime
import hashlib
import logging
import os
import re
import uuid
from typing import Any, Callable, Dict, List, Optional

from langchain.prompts import PromptTemplate
from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks.manager import CallbackManager
from langchain_core.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from app.api.v1.utils.prompt_manager import PromptManager
from config import settings

logger = logging.getLogger(__name__)


class LangchainService:
    """Service for generating code artifacts using Langchain with multi-language support"""

    @staticmethod
    def get_llm(streaming: bool = False, callbacks: Optional[List[Callable]] = None):
        """
        Get configured LLM with or without streaming capability.

        Args:
            streaming (bool): Whether to enable streaming output from the LLM
            callbacks (Optional[List[Callable]]): Optional list of callback functions

        Returns:
            ChatAnthropic: Configured LLM instance

        Raises:
            ValueError: If Anthropic API key is not found in environment variables
        """
        import os

        # Get API key from environment (try multiple possible names)
        api_key = getattr(settings, "ANTHROPIC_API_KEY", None) or os.getenv(
            "ANTHROPIC_KEY"
        )

        if not api_key:
            raise ValueError("Anthropic API key not found in environment variables")

        if streaming:
            callback_manager = CallbackManager([StreamingStdOutCallbackHandler()])
            if callbacks:
                for callback in callbacks:
                    callback_manager.add_handler(callback)

            return ChatAnthropic(
                model=settings.DEFAULT_LLM_PROVIDER,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
                streaming=True,
                callback_manager=callback_manager,
                api_key=api_key,  # Explicitly pass the API key
            )
        else:
            return ChatAnthropic(
                model=settings.DEFAULT_LLM_PROVIDER,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
                api_key=api_key,  # Explicitly pass the API key
            )

    @staticmethod
    def create_chain_from_template(
        template_string: str,
        streaming: bool = False,
        callbacks: Optional[List[Callable]] = None,
    ):
        """
        Create a Langchain chain from a template string.

        Args:
            template_string (str): The prompt template string
            streaming (bool): Whether to enable streaming output
            callbacks (Optional[List[Callable]]): Optional callbacks for streaming

        Returns:
            Chain: A LangChain chain that can process inputs
        """
        # Create a simple prompt template with a single input variable
        prompt = PromptTemplate.from_template("{input}")

        # Get the LLM
        llm = LangchainService.get_llm(streaming=streaming, callbacks=callbacks)

        # Create a simple chain
        chain = {"input": RunnablePassthrough()} | prompt | llm | StrOutputParser()

        return chain

    @staticmethod
    def create_streaming_chain(template_string: str, callback):
        """
        Create a streaming chain with a custom callback.

        Args:
            template_string (str): The prompt template string
            callback: Callback function to process streaming tokens

        Returns:
            Chain: A LangChain chain configured for streaming
        """
        # Create a simple prompt for streaming
        prompt = PromptTemplate.from_template("{input}")

        # Get the LLM with streaming enabled
        llm = LangchainService.get_llm(streaming=True, callbacks=[callback])

        # Create a chain
        chain = {"input": RunnablePassthrough()} | prompt | llm | StrOutputParser()

        return chain

    @staticmethod
    def encode_content(content: str) -> str:
        """
        Encode content to base64.

        Args:
            content (str): The string content to encode

        Returns:
            str: Base64 encoded string
        """
        return base64.b64encode(content.encode("utf-8")).decode("utf-8")

    @staticmethod
    def generate_file_hash(code: str) -> str:
        """
        Generates an MD5 hash from code content.

        Args:
            code (str): The code content to hash

        Returns:
            str: MD5 hash of the code content
        """
        return hashlib.md5(code.encode("utf-8")).hexdigest()

    @staticmethod
    def clean_code(code_text: str) -> str:
        """
        Remove markdown code block formatting from the provided code text.

        Args:
            code_text (str): The code text that may contain markdown formatting

        Returns:
            str: Clean code text with markdown formatting removed
        """
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

    @staticmethod
    def get_file_extension(language: str) -> str:
        """
        Get the file extension for a given language.

        Args:
            language (str): The programming language name

        Returns:
            str: File extension including the dot
        """
        extensions = {
            "python": ".py",
            "javascript": ".js",
            "typescript": ".ts",
            "java": ".java",
            "go": ".go",
            "csharp": ".cs",
            "ruby": ".rb",
            "php": ".php",
        }
        return extensions.get(language.lower(), ".txt")

    @staticmethod
    async def generate_code_with_template(
        template_name: str, language: str, **template_vars
    ) -> Dict[str, Any]:
        """
        Generate code using a template from PromptManager.

        Args:
            template_name (str): The name of the template to use
            language (str): Programming language to generate code for
            **template_vars: Variables to pass to the template

        Returns:
            Dict[str, Any]: Dictionary with generated code and metadata

        Raises:
            Exception: If code generation fails
        """
        try:
            # Format the template using PromptManager
            formatted_prompt = PromptManager.format_template(
                template_name=template_name, language=language, **template_vars
            )

            # Create a chain
            chain = LangchainService.create_chain_from_template("")

            # Execute the chain with our formatted prompt
            result = await chain.ainvoke({"input": formatted_prompt})

            # Clean the result
            cleaned_code = LangchainService.clean_code(result)

            return {
                "generated_code": cleaned_code,
                "content_base64": LangchainService.encode_content(cleaned_code),
                "language": language,
                "file_hash": LangchainService.generate_file_hash(cleaned_code),
            }
        except Exception as e:
            logger.error(
                f"Error in template-based code generation: {str(e)}", exc_info=True
            )
            raise Exception(
                f"Failed to generate code with template {template_name}: {str(e)}"
            )

    @staticmethod
    async def generate_custom_code(
        project_id: str,
        prompt: str,
        language: str = "python",
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate custom code using a specific prompt.

        Args:
            project_id (str): The project ID
            prompt (str): Custom generation prompt
            language (str): Programming language
            context (Optional[str]): Additional context code

        Returns:
            Dict[str, Any]: Dictionary with generated code and metadata

        Raises:
            Exception: If code generation fails
        """
        try:
            # Add language-specific context
            language_context = LangchainService._get_language_context(language)

            # Build the final prompt with all context
            final_prompt = f"""
            {language_context}

            {prompt}
            """

            if context:
                final_prompt += f"\n\nReference code:\n{context}"

            # Create a chain
            chain = LangchainService.create_chain_from_template("")

            # Execute the chain with our formatted prompt
            result = await chain.ainvoke({"input": final_prompt})

            # Clean the result
            cleaned_code = LangchainService.clean_code(result)

            return {
                "generated_code": cleaned_code,
                "content_base64": LangchainService.encode_content(cleaned_code),
                "language": language,
                "file_hash": LangchainService.generate_file_hash(cleaned_code),
            }
        except Exception as e:
            logger.error(f"Error in custom code generation: {e}", exc_info=True)
            raise Exception(f"Failed to generate custom code: {str(e)}")

    @staticmethod
    def _get_language_context(language: str) -> str:
        """
        Get language-specific context for the LLM.

        Args:
            language (str): Programming language

        Returns:
            str: Context string specific to the language
        """
        language = language.lower()

        if language == "python":
            return """
            You are generating Python code for a FastAPI application.
            Follow these conventions:
            - Use async/await for database operations
            - Use SQLAlchemy for ORM
            - Use Pydantic for data validation
            - Organize code into models, schemas, and endpoints
            - Follow PEP 8 style guidelines
            """
        elif language in ["javascript", "js"]:
            return """
            You are generating JavaScript code for an Express.js application.
            Follow these conventions:
            - Use ES6+ syntax with const/let
            - Use async/await for asynchronous operations
            - Use Mongoose for MongoDB models
            - Organize code into models, controllers, and routes
            - Use proper error handling with try/catch
            - Export modules using module.exports or export default
            """
        elif language == "typescript":
            return """
            You are generating TypeScript code for an Express.js application.
            Follow these conventions:
            - Use proper TypeScript types and interfaces
            - Use ES6+ syntax with const/let
            - Use async/await for asynchronous operations
            - Use Mongoose with type definitions
            - Organize code into models, controllers, and routes
            - Use proper error handling with try/catch
            - Export modules using export or export default
            """
        else:
            return f"You are generating {language} code. Follow best practices and conventions for {language}."

    @staticmethod
    def _find_existing_model(
        entity_name: str, models_list: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Find an existing model in the project that matches the entity name.

        Args:
            entity_name (str): The entity name to search for
            models_list (List[Dict[str, Any]]): List of models from project analysis

        Returns:
            Optional[Dict[str, Any]]: Matching model or None if not found
        """
        # Normalize entity name for comparison
        entity_name_lower = entity_name.lower()

        for model in models_list:
            model_name = model.get("name", "").lower()

            # Check for exact match
            if model_name == entity_name_lower:
                return model

            # Check for singular/plural variations
            if model_name.endswith("s") and model_name[:-1] == entity_name_lower:
                return model

            if entity_name_lower.endswith("s") and entity_name_lower[:-1] == model_name:
                return model

        return None

    # The following methods are maintained for backward compatibility
    # They use the language template system internally but keep the same interface

    @staticmethod
    async def generate_endpoint(
        project_id: str,
        endpoint_description: str,
        method: str,
        endpoint_path: str,
        language: str = "python",
        additional_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate endpoint code using Langchain with language support.

        Args:
            project_id (str): Identifier for the project
            endpoint_description (str): Description of the endpoint functionality
            method (str): HTTP method for the endpoint (GET, POST, etc.)
            endpoint_path (str): URL path for the endpoint
            language (str): Programming language to generate code for
            additional_context (Optional[str]): Any supplementary information

        Returns:
            Dict[str, Any]: Dictionary with generated endpoint code and metadata

        Raises:
            Exception: If endpoint generation fails
        """
        try:
            # Use our new template-based generation
            result = await LangchainService.generate_code_with_template(
                template_name="endpoint",
                endpoint_description=endpoint_description,
                method=method,
                method_lower=method.lower(),
                endpoint_path=endpoint_path,
                additional_context=additional_context or "",
                language=language,
            )

            # Add backward compatibility fields
            path_segments = endpoint_path.strip("/").split("/")
            last_segment = path_segments[-1]
            file_extension = LangchainService.get_file_extension(language)
            file_path = f"endpoints/{last_segment}.{method.lower()}{file_extension}"

            result["method"] = method
            result["endpoint_path"] = endpoint_path
            result["file_path"] = file_path

            return result

        except Exception as e:
            logger.error(
                f"Error generating endpoint with Langchain: {str(e)}", exc_info=True
            )
            raise Exception(f"Failed to generate endpoint with Langchain: {str(e)}")

    @staticmethod
    async def generate_model(
        project_id: str,
        entity_name: str,
        entity_description: str,
        language: str = "python",
        endpoint_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate model code using Langchain with language support.

        Args:
            project_id (str): Identifier for the project
            entity_name (str): Name of the entity to model
            entity_description (str): Description of the entity
            language (str): Programming language to generate code for
            endpoint_code (Optional[str]): Optional endpoint code for context

        Returns:
            Dict[str, Any]: Dictionary with generated model code and metadata

        Raises:
            Exception: If model generation fails
        """
        try:
            # Use our new template-based generation
            result = await LangchainService.generate_code_with_template(
                template_name="model",
                language=language,
                entity_name=entity_name,
                entity_description=entity_description,
                endpoint_code=endpoint_code
                or "# Endpoint code not provided for context",
            )

            # Add backward compatibility fields
            file_extension = LangchainService.get_file_extension(language)
            file_path = f"models/{entity_name.lower()}{file_extension}"

            result["entity_name"] = entity_name
            result["file_path"] = file_path

            return result

        except Exception as e:
            logger.error(
                f"Error generating model with Langchain: {str(e)}", exc_info=True
            )
            raise Exception(f"Failed to generate model with Langchain: {str(e)}")

    @staticmethod
    async def generate_schema(
        project_id: str,
        entity_name: str,
        language: str = "python",
        endpoint_code: Optional[str] = None,
        model_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate schema code using Langchain with language support.

        Args:
            project_id (str): Identifier for the project
            entity_name (str): Name of the entity to create schemas for
            language (str): Programming language to generate code for
            endpoint_code (Optional[str]): Optional endpoint code for context
            model_code (Optional[str]): Optional model code for context

        Returns:
            Dict[str, Any]: Dictionary with generated schema code and metadata

        Raises:
            Exception: If schema generation fails
        """
        try:
            # Use our new template-based generation
            result = await LangchainService.generate_code_with_template(
                template_name="schema",
                language=language,
                entity_name=entity_name,
                endpoint_code=endpoint_code or "# Endpoint code not provided",
                model_code=model_code or "# Model code not provided",
            )

            # Add backward compatibility fields
            file_extension = LangchainService.get_file_extension(language)
            file_path = f"schemas/{entity_name.lower()}{file_extension}"

            result["entity_name"] = entity_name
            result["file_path"] = file_path

            return result

        except Exception as e:
            logger.error(
                f"Error generating schema with Langchain: {str(e)}", exc_info=True
            )
            raise Exception(f"Failed to generate schema with Langchain: {str(e)}")

    # @staticmethod
    # async def generate_migration(
    #     project_id: str,
    #     entity_name: str,
    #     language: str = "python",
    #     model_code: Optional[str] = None,
    # ) -> Dict[str, Any]:
    #     """
    #     Generate migration code using Langchain with language support.

    #     Args:
    #         project_id (str): Identifier for the project
    #         entity_name (str): Name of the entity to create migrations for
    #         language (str): Programming language to generate code for
    #         model_code (Optional[str]): Optional model code for context

    #     Returns:
    #         Dict[str, Any]: Dictionary with generated migration code and metadata

    #     Raises:
    #         Exception: If migration generation fails
    #     """
    #     try:
    #         # Determine the project path based on the project_id
    #         project_path = f"repos/{project_id}"
    #         alembic_dir = os.path.join(project_path, "alembic")

    #         # Determine the latest migration ID
    #         try:
    #             from app.api.v1.utils.migration_finder import get_latest_migration_id

    #             latest_migration_id = get_latest_migration_id(alembic_dir=alembic_dir)
    #         except Exception as e:
    #             logger.warning(
    #                 f"Could not determine latest migration ID: {str(e)}. Using 'base' as default."
    #             )
    #             latest_migration_id = "base"

    #         logger.info(f"Using latest migration ID as parent: {latest_migration_id}")

    #         # Use our new template-based generation
    #         result = await LangchainService.generate_code_with_template(
    #             template_name="migration",
    #             language=language,
    #             entity_name=entity_name,
    #             latest_migration_id=latest_migration_id,
    #             model_code=model_code or "# Model code not provided",
    #         )

    #         timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    #         revision_id = uuid.uuid4().hex[:8]

    #         # Use the appropriate file extension
    #         file_extension = LangchainService.get_file_extension(language)
    #         filename = f"{timestamp}_{revision_id}_create_{entity_name.lower()}{file_extension}"

    #         # File path: alembic/versions/timestamp_revision_create_entity.[extension]
    #         file_path = f"alembic/versions/{filename}"

    #         result["entity_name"] = entity_name
    #         result["file_path"] = file_path
    #         result["parent_migration_id"] = latest_migration_id

    #         return result

    #     except Exception as e:
    #         logger.error(
    #             f"Error generating migration with Langchain: {str(e)}", exc_info=True
    #         )
    #         raise Exception(f"Failed to generate migration with Langchain: {str(e)}")

    @staticmethod
    async def generate_helpers(
        project_id: str,
        entity_name: str,
        entity_description: str,
        language: str = "python",
        endpoint_code: Optional[str] = None,
        model_code: Optional[str] = None,
        schema_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate helper functions using Langchain with language support.

        Args:
            project_id (str): Identifier for the project
            entity_name (str): Name of the entity to create helpers for
            entity_description (str): Description of the entity
            language (str): Programming language to generate code for
            endpoint_code (Optional[str]): Optional endpoint code for context
            model_code (Optional[str]): Optional model code for context
            schema_code (Optional[str]): Optional schema code for context

        Returns:
            Dict[str, Any]: Dictionary with generated helper code and metadata

        Raises:
            Exception: If helper function generation fails
        """
        try:
            # Use our new template-based generation
            result = await LangchainService.generate_code_with_template(
                template_name="helpers",
                language=language,
                entity_name=entity_name,
                entity_description=entity_description,
                endpoint_code=endpoint_code or "# Endpoint code not provided",
                model_code=model_code or "# Model code not provided",
                schema_code=schema_code or "# Schema code not provided",
            )

            # Add backward compatibility fields
            file_extension = LangchainService.get_file_extension(language)
            file_path = f"helpers/{entity_name.lower()}_helpers{file_extension}"

            result["entity_name"] = entity_name
            result["file_path"] = file_path

            return result

        except Exception as e:
            logger.error(
                f"Error generating helper functions with Langchain: {str(e)}",
                exc_info=True,
            )
            raise Exception(
                f"Failed to generate helper functions with Langchain: {str(e)}"
            )

    @staticmethod
    def needs_model_and_schema(code: str) -> bool:
        """
        Determine if the generated code needs database models and schemas.

        Args:
            code (str): The code to analyze

        Returns:
            bool: True if the code references database components
        """
        # Delegate to the appropriate language template if possible
        try:
            from app.api.v1.services.language_templates.language_template import (
                LanguageTemplateFactory,
            )

            # Try to determine the language from the code
            language = "python"  # Default
            if "const " in code or "let " in code or "import " in code:
                language = "javascript"

            # Get the template and use its method
            template = LanguageTemplateFactory.get_template(language)
            return template.needs_database(code)

        except ImportError:
            # Fallback to basic detection if language templates aren't available
            db_patterns = [
                # Python patterns
                r"from\s+.*models?\s+import",
                r"from\s+.*schemas?\s+import",
                r"db\.session",
                r"db\s*\.\s*query",
                # JavaScript patterns
                r"require\(['\"]\.\./models/",
                r"import\s+.*\s+from\s+['\"]\.\./models/",
                r"mongoose",
                r"sequelize",
                r"Model\.",
            ]

            for pattern in db_patterns:
                if re.search(pattern, code, re.IGNORECASE):
                    return True
            return False
