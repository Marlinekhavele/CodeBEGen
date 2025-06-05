"""
Test Script for Project Structure Awareness Feature

This script demonstrates how the project structure awareness features work
by analyzing a specified directory and generating a sample response.

To test the script, run it from the command line with the following command:
python test_project_context.py --path /path/to/your/project --query "What is the purpose of this codebase?"

For example:
python test_project_context.py --path c:/Users/PC/Documents/CodeGenBE/code-gen-be --query "What is the purpose of this codebase?"
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from app.api.v1.services.context_aware_langchain_service import (
    ContextAwareLangchainService,
)
from app.api.v1.utils.project_structure import get_formatted_project_structure

# Add the project root to the Python path to import the app modules
SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.append(str(PROJECT_ROOT))


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Test project structure awareness feature"
    )
    parser.add_argument(
        "--path",
        type=str,
        default=str(PROJECT_ROOT),
        help="Path to the project directory to analyze",
    )
    parser.add_argument(
        "--query",
        type=str,
        default="What's the main purpose of this codebase?",
        help="Sample query to test with the LLM",
    )
    args = parser.parse_args()

    project_path = Path(args.path)

    if not project_path.exists() or not project_path.is_dir():
        logger.error(f"Invalid project path: {project_path}")
        sys.exit(1)

    print(f"Analyzing project structure at: {project_path}")

    # Get the project structure
    structure = get_formatted_project_structure(project_path)
    print("\nProject Structure Summary:")
    print("-" * 80)
    print(structure)
    print("-" * 80)

    # Create a context-aware chain
    print(f"\nTesting LLM with query: '{args.query}'")
    print("\nCreating context-aware chain...")

    try:
        chain = ContextAwareLangchainService.create_chain_with_project_context(
            "", project_path, streaming=True
        )

        print("\nGenerating response (streaming):")
        print("-" * 80)
        chain.invoke({"input": args.query})
        print("-" * 80)
        print("\nDone!")
    except Exception as e:
        logger.error(f"Error generating response: {e}", exc_info=True)
        print(f"\nError: {e}")


if __name__ == "__main__":
    main()
