import base64
import hashlib
import logging
import re
from typing import Any, Callable, Dict, List, Optional

from langchain.prompts import PromptTemplate
from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks.manager import CallbackManager
from langchain_core.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from app.api.v1.services.project_structure_context_service import (
    ProjectStructureContextService,
)
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
    def enhance_prompt_with_project_context(
        prompt: str, project_id: Optional[str]
    ) -> str:
        """
        Enhance a prompt with project structure context if available.

        Args:
            prompt (str): The original prompt text
            project_id (Optional[str]): The project identifier

        Returns:
            str: Enhanced prompt with project structure context
        """
        if not project_id:
            return prompt

        try:
            return ProjectStructureContextService.enhance_prompt_with_structure(
                prompt, project_id
            )
        except Exception as e:
            logger.error(f"Failed to enhance prompt with project structure: {e}")
            return prompt

    @staticmethod
    async def generate_code_with_template(
        template_name: str,
        language: str,
        project_id: Optional[str] = None,
        **template_vars,
    ) -> Dict[str, Any]:
        """
        Generate code using a template from PromptManager, enhanced with project context.

        Args:
            template_name (str): The name of the template to use
            language (str): Programming language to generate code for
            project_id (Optional[str]): The project identifier
            **template_vars: Variables to pass to the template

        Returns:
            Dict[str, Any]: Dictionary with generated code and metadata

        Raises:
            Exception: If code generation fails
        """
        try:
            # Format the template using PromptManager, including project_id
            template_vars_with_project_id = {**template_vars}
            if project_id:
                template_vars_with_project_id["project_id"] = project_id

            formatted_prompt = PromptManager.format_template(
                template_name=template_name,
                language=language,
                **template_vars_with_project_id,
            )

            # Enhance the prompt with project structure context
            enhanced_prompt = LangchainService.enhance_prompt_with_project_context(
                formatted_prompt, project_id
            )

            # Create a chain
            chain = LangchainService.create_chain_from_template("")

            # Execute the chain with our enhanced prompt
            result = await chain.ainvoke({"input": enhanced_prompt})

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
    def generate_code_with_template_sync(
        template_name: str,
        language: str,
        project_id: Optional[str] = None,
        **template_vars,
    ) -> Dict[str, Any]:
        """
        Generate code using a template from PromptManager, enhanced with project context - synchronous version.

        Args:
            template_name (str): The name of the template to use
            language (str): Programming language to generate code for
            project_id (Optional[str]): The project identifier
            **template_vars: Variables to pass to the template

        Returns:
            Dict[str, Any]: Dictionary with generated code and metadata

        Raises:
            Exception: If code generation fails
        """
        try:

            # Format the template using PromptManager, including project_id
            template_vars_with_project_id = {**template_vars}
            if project_id:
                template_vars_with_project_id["project_id"] = project_id

            formatted_prompt = PromptManager.format_template(
                template_name=template_name,
                language=language,
                **template_vars_with_project_id,
            )

            # Enhance the prompt with project structure context
            enhanced_prompt = LangchainService.enhance_prompt_with_project_context(
                formatted_prompt, project_id
            )

            # Create a chain
            chain = LangchainService.create_chain_from_template("")

            # Execute the chain with our enhanced prompt - synchronously
            result = chain.invoke({"input": enhanced_prompt})

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
            ) @ staticmethod

    def generate_helpers_sync(
        project_id: Optional[str] = None,
        entity_name: str = "",
        entity_description: Optional[str] = None,
        endpoint_code: str = "",
        model_code: str = "",
        schema_code: str = "",
        only_functions: Optional[List[str]] = None,
        language: str = "python",
    ) -> Dict[str, Any]:
        """
        Generate helper functions synchronously based on entity and endpoint requirements.
        Args:
            project_id: Optional project identifier for context
            entity_name: The name of the entity being created
            entity_description: Optional description of the entity
            endpoint_code: The endpoint code that references helper functions
            model_code: The model code for context
            schema_code: The schema code for context
            only_functions: Optional list of specific functions to generate
            language: The programming language to generate helpers in
        Returns:
            Dict with generated helper code and metadata
        """
        try:
            # Always use the correct template name for helpers
            template_name = "helpers"

            # Format template variables
            template_vars = {
                "entity_name": entity_name,
                "entity_description": entity_description or f"{entity_name} entity",
                "endpoint_code": endpoint_code,
                "model_code": model_code,
                "schema_code": schema_code,
            }
            # Add specific functions if provided
            if only_functions:
                template_vars["only_functions"] = ", ".join(only_functions)
                logger.info(
                    f"Generating only specific helper functions: {only_functions}"
                )

            # Generate the code
            result = LangchainService.generate_code_with_template_sync(
                template_name=template_name,
                language=language,
                project_id=project_id,
                **template_vars,
            )
            # Clean and extract code
            generated_code = result.get("generated_code", "")
            # Return all required fields for downstream code/tests
            return {
                "generated_code": generated_code,
                "content_base64": result.get("content_base64", ""),
                "file_hash": result.get("file_hash", ""),
                "language": result.get("language", language),
                "file_path": result.get(
                    "file_path", f"helpers/{entity_name.lower()}_helpers.py"
                ),
                "only_functions": only_functions,
                "success": True,
            }
        except Exception as e:
            logger.error(f"Error generating helpers: {str(e)}", exc_info=True)
            return {
                "generated_code": f"# Error generating helpers: {str(e)}",
                "success": False,
                "error": str(e),
            }

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

    @staticmethod
    async def fix_code_error(
        project_id: str,
        error_message: str,
        generated_code: str,
        language: str = "python",
        file_path: Optional[str] = None,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fix code errors using LLM, especially configuration and compatibility issues.

        Args:
            project_id: The project identifier
            error_message: The error message from testing/execution
            generated_code: The code that has the error
            language: Programming language (python, javascript, etc.)
            file_path: Path to the file with error (optional)
            context: Additional context about the error (optional)

        Returns:
            Dict containing the fixed code and metadata
        """
        try:
            # Create error-specific prompt based on error type
            error_type = LangchainService._classify_error_type(error_message)

            if error_type == "pydantic_config":
                # Special handling for Pydantic configuration errors
                prompt_template = """
You are an expert Python developer fixing Pydantic configuration errors.

ERROR MESSAGE: {error_message}

CURRENT CODE:
```python
{generated_code}
```

TASK: Fix the Pydantic configuration error. Common fixes:
1. For "You must set the config attribute `from_attributes=True` to use from_orm":
   - Replace `orm_mode = True` with `from_attributes = True` in Config class
   - Update to Pydantic v2 syntax

2. For other Pydantic v2 migration issues:
   - Update Config class syntax
   - Fix field definitions
   - Update validators

OUTPUT: Provide ONLY the fixed Python code without explanations or markdown formatting.
"""
            elif error_type == "parameter_mismatch":
                # Handle function parameter mismatches
                prompt_template = """
You are an expert Python developer fixing function parameter mismatch errors.

ERROR MESSAGE: {error_message}

CURRENT CODE:
```python
{generated_code}
```

TASK: Fix the parameter mismatch error by:
1. Analyzing function calls and definitions
2. Ensuring parameter names match between caller and callee
3. Fixing any parameter name inconsistencies

OUTPUT: Provide ONLY the fixed Python code without explanations or markdown formatting.
"""
            elif error_type == "import_error":
                # Handle import errors
                prompt_template = """
You are an expert Python developer fixing import errors.

ERROR MESSAGE: {error_message}

CURRENT CODE:
```python
{generated_code}
```

FILE PATH: {file_path}
PROJECT CONTEXT: {context}

TASK: Fix the import error by:
1. Correcting import statements
2. Ensuring proper module paths
3. Adding missing imports
4. Removing unused imports

OUTPUT: Provide ONLY the fixed Python code without explanations or markdown formatting.
"""
            else:
                # Generic error fixing
                prompt_template = """
You are an expert {language} developer fixing code errors.

ERROR MESSAGE: {error_message}

CURRENT CODE:
```{language}
{generated_code}
```

FILE PATH: {file_path}
ADDITIONAL CONTEXT: {context}

TASK: Analyze the error message and fix the code to resolve the issue. Common fixes include:
1. Syntax errors
2. Configuration issues
3. Import problems
4. Function signature mismatches
5. Type errors

OUTPUT: Provide ONLY the fixed {language} code without explanations or markdown formatting.
"""

            # Create the prompt
            prompt = PromptTemplate(
                input_variables=[
                    "error_message",
                    "generated_code",
                    "language",
                    "file_path",
                    "context",
                ],
                template=prompt_template,
            )

            # Get LLM
            llm = LangchainService.get_llm()

            # Create chain
            chain = prompt | llm | StrOutputParser()

            # Generate fixed code
            result = await chain.ainvoke(
                {
                    "error_message": error_message,
                    "generated_code": generated_code,
                    "language": language,
                    "file_path": file_path or "Unknown",
                    "context": context or "No additional context",
                }
            )

            # Clean up the result (remove any markdown formatting)
            fixed_code = LangchainService._clean_generated_code(result, language)

            return {
                "generated_code": fixed_code,
                "file_path": file_path,
                "content_base64": LangchainService.encode_content(fixed_code),
                "file_hash": LangchainService.generate_file_hash(fixed_code),
                "error_type": error_type,
                "fixed": True,
            }

        except Exception as e:
            logger.error(f"Error fixing code: {str(e)}", exc_info=True)
            raise Exception(f"Failed to fix code error: {str(e)}")

    @staticmethod
    def _classify_error_type(error_message: str) -> str:
        """
        Classify the type of error based on the error message.

        Args:
            error_message: The error message to classify

        Returns:
            str: The error type classification
        """
        error_lower = error_message.lower()

        if "from_attributes" in error_lower and "use from_orm" in error_lower:
            return "pydantic_config"
        elif "got an unexpected keyword argument" in error_lower:
            return "parameter_mismatch"
        elif "no module named" in error_lower or "import" in error_lower:
            return "import_error"
        elif "syntax error" in error_lower:
            return "syntax_error"
        elif "type error" in error_lower:
            return "type_error"
        else:
            return "generic"

    @staticmethod
    def _clean_generated_code(code: str, language: str) -> str:
        """
        Clean up generated code by removing markdown formatting and extra text.

        Args:
            code: The raw generated code
            language: The programming language

        Returns:
            str: Cleaned code
        """
        # Remove markdown code blocks
        code = re.sub(rf"```{language}\n?", "", code)
        code = re.sub(r"```\n?", "", code)

        # Remove any explanatory text before/after code
        lines = code.split("\n")

        # Find the first line that looks like code
        start_idx = 0
        for i, line in enumerate(lines):
            if language == "python":
                # Look for imports, class, def, or other Python statements
                if (
                    line.strip().startswith(
                        ("import ", "from ", "class ", "def ", "@", "async def")
                    )
                    or line.strip()
                    and not line.strip().startswith(("Here", "The", "This", "Fixed"))
                ):
                    start_idx = i
                    break
            else:
                # For other languages, be more generic
                if line.strip() and not line.strip().startswith(
                    ("Here", "The", "This", "Fixed")
                ):
                    start_idx = i
                    break

        # Find the last line that looks like code
        end_idx = len(lines) - 1
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() and not lines[i].strip().startswith(
                ("The above", "This should")
            ):
                end_idx = i
                break

        # Extract the code section
        cleaned_lines = lines[start_idx : end_idx + 1]
        return "\n".join(cleaned_lines).strip()
