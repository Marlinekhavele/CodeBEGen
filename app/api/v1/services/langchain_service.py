import base64
import hashlib
import logging
import os
from typing import Any, Callable, Dict, List, Optional

from langchain.prompts import PromptTemplate
from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks.manager import CallbackManager
from langchain_core.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from config import settings

logger = logging.getLogger(__name__)


class LangchainService:
    """
    Service for generating code artifacts using Langchain with multi-language support
    """

    @staticmethod
    def get_llm(streaming: bool = False, callbacks: Optional[List[Callable]] = None):
        """Get configured LLM with or without streaming"""
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
        """Create a Langchain chain from a template string"""
        # Create a simple prompt template with a single input variable
        prompt = PromptTemplate.from_template("{input}")

        # Get the LLM
        llm = LangchainService.get_llm(streaming=streaming, callbacks=callbacks)

        # Create a simple chain
        chain = {"input": RunnablePassthrough()} | prompt | llm | StrOutputParser()

        return chain

    @staticmethod
    def create_streaming_chain(template_string: str, callback):
        """Create a streaming chain with a custom callback"""
        # Create a simple prompt for streaming
        prompt = PromptTemplate.from_template("{input}")

        # Get the LLM with streaming enabled
        llm = LangchainService.get_llm(streaming=True, callbacks=[callback])

        # Create a chain
        chain = {"input": RunnablePassthrough()} | prompt | llm | StrOutputParser()

        return chain

    @staticmethod
    def encode_content(content: str) -> str:
        """Encode content to base64"""
        return base64.b64encode(content.encode("utf-8")).decode("utf-8")

    @staticmethod
    def generate_file_hash(code: str) -> str:
        """Generates an MD5 hash from code content"""
        return hashlib.md5(code.encode("utf-8")).hexdigest()

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

    @staticmethod
    def get_file_extension(language: str) -> str:
        """Get the file extension for a given language"""
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
    async def generate_endpoint(
        project_id: str,
        endpoint_description: str,
        method: str,
        endpoint_path: str,
        language: str = "python",
        additional_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate endpoint code using Langchain with language support"""
        try:
            # Get the appropriate template for this language
            from app.api.v1.utils.prompt_manager import PromptManager

            template = PromptManager.get_template("endpoint", language)

            # If the template is already a PromptTemplate object, we need to extract its template string
            if hasattr(template, "template"):
                template_string = template.template
            else:
                template_string = str(template)

            # Create a manually formatted string from the template
            formatted_prompt = template_string.format(
                endpoint_description=endpoint_description,
                method=method,
                method_lower=method.lower(),
                endpoint_path=endpoint_path,
                additional_context=additional_context or "",
                language=language,
            )

            # Create a chain
            chain = LangchainService.create_chain_from_template(template_string)

            # Execute the chain with our formatted prompt as the input
            result = await chain.ainvoke({"input": formatted_prompt})

            # Clean the result
            cleaned_code = LangchainService.clean_code(result)

            # Generate file info with appropriate extension
            file_extension = LangchainService.get_file_extension(language)
            path_segments = endpoint_path.strip("/").split("/")
            last_segment = path_segments[-1]
            file_path = f"endpoints/{last_segment}.{method.lower()}{file_extension}"

            return {
                "generated_code": cleaned_code,
                "content_base64": LangchainService.encode_content(cleaned_code),
                "method": method,
                "endpoint_path": endpoint_path,
                "language": language,
                "file_path": file_path,
                "file_hash": LangchainService.generate_file_hash(cleaned_code),
            }

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
        """Generate model code using Langchain with language support"""
        try:
            # Get the appropriate template for this language
            from app.api.v1.utils.prompt_manager import PromptManager

            template = PromptManager.get_template("model", language)

            # If template is a PromptTemplate object, extract the template string
            if hasattr(template, "template"):
                template_string = template.template
            else:
                template_string = str(template)

            # Format the template with the specific values
            formatted_prompt = template_string.format(
                entity_name=entity_name,
                entity_description=entity_description,
                endpoint_code=endpoint_code
                or "# Endpoint code not provided for context",
                language=language,
            )

            # Create a chain
            chain = LangchainService.create_chain_from_template(template_string)

            # Execute the chain with our formatted prompt
            result = await chain.ainvoke({"input": formatted_prompt})

            # Clean the result
            cleaned_code = LangchainService.clean_code(result)

            # Generate file info with appropriate extension
            file_extension = LangchainService.get_file_extension(language)
            file_path = f"models/{entity_name.lower()}{file_extension}"

            return {
                "generated_code": cleaned_code,
                "content_base64": LangchainService.encode_content(cleaned_code),
                "entity_name": entity_name,
                "language": language,
                "file_path": file_path,
                "file_hash": LangchainService.generate_file_hash(cleaned_code),
            }

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
        """Generate schema code using Langchain with language support"""
        try:
            # Get the appropriate template for this language
            from app.api.v1.utils.prompt_manager import PromptManager

            template = PromptManager.get_template("schema", language)

            # If template is a PromptTemplate object, extract the template string
            if hasattr(template, "template"):
                template_string = template.template
            else:
                template_string = str(template)

            # Format the template with the specific values
            formatted_prompt = template_string.format(
                entity_name=entity_name,
                endpoint_code=endpoint_code or "# Endpoint code not provided",
                model_code=model_code or "# Model code not provided",
                language=language,
            )

            # Create a chain
            chain = LangchainService.create_chain_from_template(template_string)

            # Execute the chain with our formatted prompt
            result = await chain.ainvoke({"input": formatted_prompt})

            # Clean the result
            cleaned_code = LangchainService.clean_code(result)

            # Generate file info with appropriate extension
            file_extension = LangchainService.get_file_extension(language)
            file_path = f"schemas/{entity_name.lower()}{file_extension}"

            return {
                "generated_code": cleaned_code,
                "content_base64": LangchainService.encode_content(cleaned_code),
                "entity_name": entity_name,
                "language": language,
                "file_path": file_path,
                "file_hash": LangchainService.generate_file_hash(cleaned_code),
            }

        except Exception as e:
            logger.error(
                f"Error generating schema with Langchain: {str(e)}", exc_info=True
            )
            raise Exception(f"Failed to generate schema with Langchain: {str(e)}")

    @staticmethod
    async def generate_migration(
        project_id: str,
        entity_name: str,
        language: str = "python",
        model_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate migration code using Langchain with language support"""
        try:
            # Determine the project path based on the project_id
            project_path = f"repos/{project_id}"
            alembic_dir = os.path.join(project_path, "alembic")

            # Determine the latest migration ID
            try:
                from app.api.v1.utils.migration_finder import get_latest_migration_id

                latest_migration_id = get_latest_migration_id(alembic_dir=alembic_dir)
            except Exception as e:
                logger.warning(
                    f"Could not determine latest migration ID: {str(e)}. Using 'base' as default."
                )
                latest_migration_id = "base"

            logger.info(f"Using latest migration ID as parent: {latest_migration_id}")

            # Get the appropriate template for this language
            from app.api.v1.utils.prompt_manager import PromptManager

            template = PromptManager.get_template("migration", language)

            # If template is a PromptTemplate object, extract the template string
            if hasattr(template, "template"):
                template_string = template.template
            else:
                template_string = str(template)

            # Format the template with the specific values
            formatted_prompt = template_string.format(
                entity_name=entity_name,
                latest_migration_id=latest_migration_id,
                model_code=model_code or "# Model code not provided",
                language=language,
            )

            # Create a chain
            chain = LangchainService.create_chain_from_template(template_string)

            # Execute the chain with our formatted prompt
            result = await chain.ainvoke({"input": formatted_prompt})

            # Clean the result
            cleaned_code = LangchainService.clean_code(result)

            # Generate a unique filename for the migration
            import datetime
            import uuid

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            revision_id = uuid.uuid4().hex[:8]

            # Use the appropriate file extension
            file_extension = LangchainService.get_file_extension(language)
            filename = f"{timestamp}_{revision_id}_create_{entity_name.lower()}{file_extension}"

            # File path: alembic/versions/timestamp_revision_create_entity.[extension]
            file_path = f"alembic/versions/{filename}"

            return {
                "generated_code": cleaned_code,
                "content_base64": LangchainService.encode_content(cleaned_code),
                "entity_name": entity_name,
                "language": language,
                "file_path": file_path,
                "file_hash": LangchainService.generate_file_hash(cleaned_code),
                "parent_migration_id": latest_migration_id,
            }

        except Exception as e:
            logger.error(
                f"Error generating migration with Langchain: {str(e)}", exc_info=True
            )
            raise Exception(f"Failed to generate migration with Langchain: {str(e)}")

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
        """Generate helper functions using Langchain with language support"""
        try:
            # Get the appropriate template for this language
            from app.api.v1.utils.prompt_manager import PromptManager

            template = PromptManager.get_template("helpers", language)

            # If template is a PromptTemplate object, extract the template string
            if hasattr(template, "template"):
                template_string = template.template
            else:
                template_string = str(template)

            # Format the template with the specific values
            formatted_prompt = template_string.format(
                entity_name=entity_name,
                entity_description=entity_description,
                endpoint_code=endpoint_code or "# Endpoint code not provided",
                model_code=model_code or "# Model code not provided",
                schema_code=schema_code or "# Schema code not provided",
                language=language,
            )

            # Create a chain
            chain = LangchainService.create_chain_from_template(template_string)

            # Execute the chain with our formatted prompt
            result = await chain.ainvoke({"input": formatted_prompt})

            # Clean the result
            cleaned_code = LangchainService.clean_code(result)

            # Generate file info with appropriate extension
            file_extension = LangchainService.get_file_extension(language)
            file_path = f"helpers/{entity_name.lower()}_helpers{file_extension}"

            return {
                "generated_code": cleaned_code,
                "content_base64": LangchainService.encode_content(cleaned_code),
                "entity_name": entity_name,
                "language": language,
                "file_path": file_path,
                "file_hash": LangchainService.generate_file_hash(cleaned_code),
            }

        except Exception as e:
            logger.error(
                f"Error generating helper functions with Langchain: {str(e)}",
                exc_info=True,
            )
            raise Exception(
                f"Failed to generate helper functions with Langchain: {str(e)}"
            )
