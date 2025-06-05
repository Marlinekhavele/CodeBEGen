"""
Project Structure Analyzer

This module provides functionality to:
1. Analyze and retrieve the current folder structure of a project
2. Intelligently summarize large folder structures
3. Cache the results for better performance
4. Provide proper format for LangChain prompt templates
"""

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)

# Cache for project structures with expiry time (in seconds)
_project_structure_cache: Dict[str, Tuple[str, float]] = {}
CACHE_EXPIRY_TIME = 300  # 5 minutes


class ProjectStructureAnalyzer:
    """
    Analyzes the folder structure of a project and formats it appropriately for LLM prompts.
    """

    # Common patterns to exclude from the structure (can be extended)
    DEFAULT_EXCLUDE_PATTERNS = {
        "__pycache__",
        ".git",
        ".vscode",
        ".idea",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
        ".coverage",
        "venv",
        ".env",
        ".DS_Store",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        "*.so",
        "*.dll",
        "*.exe",
        "*.obj",
        "*.class",
    }

    # Extensions to consider as important code files
    IMPORTANT_FILE_EXTENSIONS = {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".java",
        ".go",
        ".rb",
        ".php",
        ".cs",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".md",
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".ini",
        ".env",
        ".sql",
        ".html",
        ".css",
        ".scss",
    }

    # Large directories that need special handling
    LARGE_DIR_THRESHOLD = 50  # Files or directories

    @staticmethod
    def get_project_structure(
        project_path: Union[str, Path],
        max_depth: int = 7,
        exclude_patterns: Optional[Set[str]] = None,
        use_cache: bool = True,
        cache_expiry: int = CACHE_EXPIRY_TIME,
    ) -> str:
        """
        Retrieves or generates a structured representation of the project directory.

        Args:
            project_path: Path to the project root
            max_depth: Maximum depth to traverse
            exclude_patterns: Patterns to exclude from the structure
            use_cache: Whether to use cached results if available
            cache_expiry: Time in seconds before cache expires

        Returns:
            Formatted string representation of the project structure
        """
        project_path = Path(project_path)
        cache_key = str(project_path)

        # Check cache if enabled
        if use_cache and cache_key in _project_structure_cache:
            cached_structure, timestamp = _project_structure_cache[cache_key]
            if time.time() - timestamp < cache_expiry:
                logger.debug(f"Using cached project structure for {project_path}")
                return cached_structure

        logger.info(f"Analyzing project structure at: {project_path}")

        if exclude_patterns is None:
            exclude_patterns = ProjectStructureAnalyzer.DEFAULT_EXCLUDE_PATTERNS

        try:
            structure = ProjectStructureAnalyzer._build_structure(
                project_path, max_depth=max_depth, exclude_patterns=exclude_patterns
            )

            # Cache the result
            if use_cache:
                _project_structure_cache[cache_key] = (structure, time.time())

            return structure
        except Exception as e:
            logger.error(f"Error analyzing project structure: {e}")
            return f"Failed to analyze project structure: {e}"

    @staticmethod
    def _build_structure(
        path: Path,
        current_depth: int = 0,
        max_depth: int = 7,
        prefix: str = "",
        exclude_patterns: Set[str] = None,
    ) -> str:
        """
        Recursively builds the directory structure as a formatted string.

        Args:
            path: Current directory path
            current_depth: Current recursion depth
            max_depth: Maximum depth to traverse
            prefix: Prefix for the current line (for indentation)
            exclude_patterns: Set of patterns to exclude

        Returns:
            Formatted string representation of the structure
        """
        if current_depth > max_depth:
            return f"{prefix}...\n"

        if not path.exists() or not path.is_dir():
            return f"{prefix}[Invalid path: {path}]\n"

        result = []

        try:
            # Get all items in the directory
            items = list(path.iterdir())

            # Filter out excluded patterns
            filtered_items = []
            for item in items:
                if any(exclude in str(item) for exclude in exclude_patterns):
                    continue
                filtered_items.append(item)

            # Sort: directories first, then files
            dirs = sorted([i for i in filtered_items if i.is_dir()])
            files = sorted([i for i in filtered_items if i.is_file()])

            # Check if directory is too large and needs special handling
            if len(dirs) + len(files) > ProjectStructureAnalyzer.LARGE_DIR_THRESHOLD:
                return ProjectStructureAnalyzer._summarize_large_directory(
                    path,
                    dirs,
                    files,
                    prefix,
                    current_depth,
                    max_depth,
                    exclude_patterns,
                )

            # Process directories
            for d in dirs:
                result.append(f"{prefix}{d.name}/")
                # Recursively process subdirectories
                subdir_content = ProjectStructureAnalyzer._build_structure(
                    d, current_depth + 1, max_depth, prefix + "    ", exclude_patterns
                )
                result.append(subdir_content)

            # Process files
            for f in files:
                result.append(f"{prefix}{f.name}")

            return "\n".join(result) + "\n"
        except PermissionError:
            return f"{prefix}[Permission denied: {path}]\n"
        except Exception as e:
            return f"{prefix}[Error: {e}]\n"

    @staticmethod
    def _summarize_large_directory(
        path: Path,
        dirs: List[Path],
        files: List[Path],
        prefix: str = "",
        current_depth: int = 0,
        max_depth: int = 7,
        exclude_patterns: Set[str] = None,
    ) -> str:
        """
        Intelligently summarizes a large directory structure.

        Args:
            path: Directory path
            dirs: List of subdirectories
            files: List of files
            prefix: Prefix for the current line
            current_depth: Current recursion depth
            max_depth: Maximum depth to traverse
            exclude_patterns: Patterns to exclude

        Returns:
            Summarized string representation
        """
        result = []

        # Add directory name
        result.append(
            f"{prefix}{path.name}/ [Large directory: {len(dirs)} dirs, {len(files)} files]"
        )

        # Process important directories (first N directories)
        important_dirs = dirs[:5]  # Show first 5 directories
        for d in important_dirs:
            result.append(f"{prefix}    {d.name}/")
            if current_depth < max_depth:
                subdir_content = ProjectStructureAnalyzer._build_structure(
                    d,
                    current_depth + 1,
                    max_depth,
                    prefix + "        ",
                    exclude_patterns,
                )
                result.append(subdir_content)

        # Note if more directories are present
        if len(dirs) > 5:
            result.append(f"{prefix}    ... {len(dirs) - 5} more directories")

        # Process important files based on extensions
        important_files = [
            f
            for f in files
            if f.suffix in ProjectStructureAnalyzer.IMPORTANT_FILE_EXTENSIONS
        ]
        # Prioritize important files but limit to 10
        files_to_show = important_files[:10]

        for f in files_to_show:
            result.append(f"{prefix}    {f.name}")

        # Note if more files are present
        remaining_files = len(files) - len(files_to_show)
        if remaining_files > 0:
            result.append(f"{prefix}    ... {remaining_files} more files")

        return "\n".join(result) + "\n"

    @staticmethod
    def clear_cache() -> None:
        """Clears the project structure cache."""
        global _project_structure_cache
        _project_structure_cache = {}
        logger.info("Project structure cache cleared")


def get_formatted_project_structure(project_path: Union[str, Path]) -> str:
    """
    Get a formatted representation of the project structure for use in LLM prompts.

    Args:
        project_path: Path to the project root

    Returns:
        Formatted string of the project structure ready for LLM context
    """
    structure = ProjectStructureAnalyzer.get_project_structure(project_path)

    # Format for LLM prompt context
    formatted_structure = (
        "The current project structure is as follows:\n" "```\n" f"{structure}" "```\n"
    )

    return formatted_structure
