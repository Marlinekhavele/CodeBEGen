import logging
import re
from pathlib import Path

from app.api.v1.utils.git_operations import REPOS_DIR, run_git_command

logger = logging.getLogger(__name__)


@staticmethod
def get_project_dir_from_repo_url(repo_url: str) -> Path:
    """
    Extract project directory from repository URL.
    Example: 'https://git.example.com/user/my-project-abc123' -> 'my-project-abc123'
    """
    logger.debug(f"Extracting project directory from repo URL: {repo_url}")

    # Extract the project name from the URL
    match = re.search(r"/([^/]+)(?:\.git)?$", repo_url)
    if not match:
        logger.error(f"Invalid repository URL format: {repo_url}")
        raise ValueError(f"Invalid repository URL format: {repo_url}")

    project_name = match.group(1)
    logger.debug(f"Extracted project name: {project_name}")

    project_dir = REPOS_DIR / project_name
    logger.debug(f"Project directory path: {project_dir}")

    if not project_dir.exists():
        logger.error(f"Project directory not found: {project_dir}")
        raise ValueError(f"Project directory not found: {project_dir}")

    logger.debug(f"Project directory found at: {project_dir}")
    return project_dir


@staticmethod
def resolve_file_path(project_dir: Path, endpoint_path: str, method: str) -> Path:
    """
    Resolves an endpoint path to a file path in the repository.
    Example: ('auth/login', 'POST') -> 'endpoints/auth/login.post.py'
    """
    logger.debug(f"Resolving path for {endpoint_path} ({method})")

    # Convert URL path to filesystem path
    clean_path = endpoint_path.strip("/")
    fs_path = project_dir / "endpoints" / f"{clean_path}.{method.lower()}.py"

    # Create directory structure if needed
    fs_path.parent.mkdir(parents=True, exist_ok=True)

    logger.debug(f"Resolved file path: {fs_path}")
    return fs_path


@staticmethod
def get_latest_commit_hash(project_dir: Path) -> str:
    """Get the latest commit hash"""
    logger.debug(f"Getting latest commit hash for project: {project_dir}")
    commit_hash = run_git_command(["git", "rev-parse", "HEAD"], cwd=project_dir)
    logger.debug(f"Latest commit hash: {commit_hash}")
    return commit_hash