"""
Context-Aware LangChain Service

This module extends the LangChain service to make it aware of project structure
by injecting folder structure context into prompts before sending them to the LLM.
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough

from app.api.v1.services.langchain_service import LangchainService
from app.api.v1.utils.project_structure import get_formatted_project_structure

logger = logging.getLogger(__name__)


class ContextAwareLangchainService:
    """
    Extension of LangchainService that makes the LLM aware of the project structure
    by injecting it as context into prompts.
    """

    @staticmethod
    def create_chain_with_project_context(
        template_string: str,
        project_path: Union[str, Path],
        streaming: bool = False,
        callbacks: Optional[List[Callable]] = None,
    ):
        """
        Create a Langchain chain that includes project structure context.

        Args:
            template_string (str): The prompt template string
            project_path (Union[str, Path]): Path to the project root
            streaming (bool): Whether to enable streaming output
            callbacks (Optional[List[Callable]]): Optional callbacks for streaming

        Returns:
            Chain: A LangChain chain with project context awareness
        """
        # Get project structure as formatted string
        try:
            project_structure = get_formatted_project_structure(project_path)
        except Exception as e:
            logger.error(f"Failed to get project structure: {e}")
            project_structure = "Failed to analyze project structure."

        # Create a combined template with project structure context
        combined_template = f"""
You are a code generation assistant with knowledge of the project structure.

{project_structure}

Please use this project structure context to provide accurate, project-specific answers.

User query:
{{input}}

"""
        # Create a prompt template with the combined template
        prompt = PromptTemplate.from_template(combined_template)
        # Get the LLM
        llm = LangchainService.get_llm(streaming=streaming, callbacks=callbacks)

        # Create a chain - use a string output parser first before cleaning code
        from langchain_core.output_parsers import StrOutputParser

        chain = (
            {"input": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
            | LangchainService.clean_code
        )

        return chain

    @staticmethod
    async def generate_code_with_project_context(
        template_name: str,
        language: str,
        project_path: Union[str, Path],
        **template_vars,
    ) -> Dict[str, Any]:
        """
        Generate code with project structure context awareness.

        Args:
            template_name (str): Name of the template to use
            language (str): Programming language to generate code in
            project_path (Union[str, Path]): Path to the project root
            **template_vars: Variables to pass to the template

        Returns:
            Dict[str, Any]: Generated code result
        """
        from app.api.v1.utils.prompt_manager import PromptManager

        try:
            # Ensure templates are loaded
            if not PromptManager._initialized:
                PromptManager.load_templates()

            # Get the appropriate template
            template = PromptManager.get_template(template_name, language)
            if not template:
                logger.error(
                    f"Template '{template_name}' not found for language '{language}'"
                )
                return {
                    "error": f"Template '{template_name}' not found for language '{language}'"
                }

            # Get project structure
            project_structure = get_formatted_project_structure(project_path)

            # Add project structure to the template variables
            template_vars["project_structure"] = project_structure

            # Format the template with variables
            prompt = template.format(**template_vars)

            # Add explicit instruction to consider project structure
            prompt = f"""Please consider the following project structure when generating code:

{project_structure}

{prompt}"""

            # Create a chain
            chain = LangchainService.create_chain_from_template("")

            # Execute the chain
            result = chain.invoke({"input": prompt})

            # Clean and prepare the result
            cleaned_code = LangchainService.clean_code(result)

            return {
                "content": cleaned_code,
                "content_base64": LangchainService.encode_content(cleaned_code),
                "filename": f"{template_name}{LangchainService.get_file_extension(language)}",
                "file_hash": LangchainService.generate_file_hash(cleaned_code),
                "language": language,
                "template": template_name,
            }

        except Exception as e:
            logger.error(f"Error generating code: {e}", exc_info=True)
            return {"error": f"Failed to generate code: {str(e)}"}
