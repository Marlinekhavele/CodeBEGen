import logging
import os
import shutil
import stat
import subprocess
from pathlib import Path

import requests

from config import settings

logger = logging.getLogger(__name__)

# Define the base directory for repositories
REPOS_DIR = Path("repos")


def ensure_repos_directory():
    """Ensure the repos directory exists"""
    if not REPOS_DIR.exists():
        REPOS_DIR.mkdir(parents=True)
        logger.info(f"Created repos directory at {REPOS_DIR.absolute()}")


def create_project_directory(project_slug):
    """Create a directory for the project"""
    project_dir = REPOS_DIR / project_slug
    if not project_dir.exists():
        project_dir.mkdir(parents=True)
        logger.info(f"Created project directory at {project_dir}")
    return project_dir


def run_git_command(command, cwd=None):
    """Run a git command and return the result"""
    cmd_str = " ".join(command)
    logger.info(f"Running Git command: {cmd_str} in directory: {cwd}")
    try:
        result = subprocess.run(
            command, cwd=cwd, check=True, capture_output=True, text=True
        )
        output = result.stdout.strip()
        # Truncate long output for logging
        log_output = output[:500] + "..." if len(output) > 500 else output
        logger.info(f"Git command succeeded: {cmd_str}")
        logger.debug(f"Git command output: {log_output}")
        return output
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip()
        logger.error(f"Git command failed: {cmd_str}")
        logger.error(f"Error details: {error_msg}")
        raise Exception(f"Git command failed: {error_msg}")


def clone_template_repo(project_dir, template_repo_url=None):
    """Initialize new project from local template"""
    import shutil
    from pathlib import Path

    # Always use local template in production
    logger.info(f"Creating project from local template at {project_dir}")

    # Fix: Use an absolute path to find the project_template directory
    # Start from the root of the project (where main.py is located)
    root_dir = Path(__file__).parent.parent.parent.parent
    template_dir = root_dir / "project_template"

    logger.info(f"Using template directory: {template_dir.absolute()}")

    # Check if the template directory exists
    if not template_dir.exists():
        raise ValueError(f"Template directory not found at {template_dir.absolute()}")

    # Check if the endpoints directory exists
    if not (template_dir / "endpoints").exists():
        raise ValueError(
            f"Endpoints directory not found at {template_dir / 'endpoints'}"
        )

    # Copy core components with conflict handling
    shutil.copytree(template_dir / "core", project_dir / "core", dirs_exist_ok=True)
    shutil.copytree(
        template_dir / "endpoints", project_dir / "endpoints", dirs_exist_ok=True
    )
    shutil.copytree(template_dir / "models", project_dir / "models", dirs_exist_ok=True)
    shutil.copytree(
        template_dir / "schemas", project_dir / "schemas", dirs_exist_ok=True
    )
    shutil.copytree(
        template_dir / "helpers", project_dir / "helpers", dirs_exist_ok=True
    )
    shutil.copytree(
        template_dir / "alembic", project_dir / "alembic", dirs_exist_ok=True
    )

    # Copy main.py and requirements.txt
    shutil.copy(template_dir / "main.py", project_dir / "main.py")
    shutil.copy(template_dir / "requirements.txt", project_dir / "requirements.txt")
    shutil.copy(template_dir / "alembic.ini", project_dir / "alembic.ini")

    # Copy .gitignore if it exists
    if (template_dir / ".gitignore").exists():
        shutil.copy(template_dir / ".gitignore", project_dir / ".gitignore")

    # Initialize bare git repo
    run_git_command(["git", "init"], cwd=project_dir)
    run_git_command(["git", "add", "."], cwd=project_dir)
    run_git_command(
        ["git", "commit", "-m", "Initial commit from template"], cwd=project_dir
    )

    logger.info(f"Successfully initialized project at {project_dir}")
    return "Project initialized from local template"


def update_git_remote(project_dir, new_repo_url):
    """Update the git remote to point to the new repository"""
    logger.info(f"Updating git remote for {project_dir} to {new_repo_url}")

    # If we have a token, embed it in the URL for authentication
    if settings.GITEA_TOKEN:
        # Parse the URL to insert the token
        if new_repo_url.startswith("https://"):
            # Extract the domain part
            url_parts = new_repo_url.split("https://")
            # Format: https://token@domain.com/path
            authenticated_url = f"https://{settings.GITEA_TOKEN}@{url_parts[1]}"
            logger.info("Using authenticated URL for Git operations")
        else:
            authenticated_url = new_repo_url
            logger.warning("Non-HTTPS URL detected, token authentication may not work")
    else:
        authenticated_url = new_repo_url
        logger.warning(
            "No Gitea token found, authentication may be required during push"
        )

    # Add the remote with authentication (will fail if it already exists)
    try:
        run_git_command(
            ["git", "remote", "add", "origin", authenticated_url], cwd=project_dir
        )
        logger.info(f"Added 'origin' remote: {authenticated_url}")
    except Exception as e:
        logger.warning(f"Could not add remote, it may already exist: {str(e)}")
        # Try to set the URL for the existing remote
        try:
            run_git_command(
                ["git", "remote", "set-url", "origin", authenticated_url],
                cwd=project_dir,
            )
            logger.info(f"Updated existing 'origin' remote URL: {authenticated_url}")
        except Exception as e2:
            logger.error(f"Failed to set remote URL: {str(e2)}")
            raise

    return True


def push_to_remote(project_dir, branch="main"):
    """Push the code to the remote repository"""
    logger.info(f"Pushing code from {project_dir} to remote")
    return run_git_command(["git", "push", "-u", "origin", branch], cwd=project_dir)


def configure_git_for_project(project_dir):
    """Configure Git settings for the project to avoid credential prompts"""
    # Set Git to use credential helper with store option
    run_git_command(["git", "config", "credential.helper", "store"], cwd=project_dir)

    # Set user information if needed (optional)
    if hasattr(settings, "GIT_USER_NAME") and hasattr(settings, "GIT_USER_EMAIL"):
        run_git_command(
            ["git", "config", "user.name", settings.GIT_USER_NAME], cwd=project_dir
        )
        run_git_command(
            ["git", "config", "user.email", settings.GIT_USER_EMAIL], cwd=project_dir
        )
        run_git_command(
            ["git", "config", "--global", "init.defaultBranch", "main"], cwd=project_dir
        )

    return True


def delete_project_repo(project_slug: str):
    """
    Delete the Git repository for a project both locally and on Gitea.

    Args:
        project_slug (str): The slug of the project.

    Raises:
        Exception: If the repository cannot be deleted.
    """
    # Local repository deletion
    repo_path = REPOS_DIR / project_slug
    if repo_path.exists():
        try:
            # Adjust file permissions to ensure deletion
            def on_rm_error(func, path, exc_info):
                # Change the file to writable and retry
                os.chmod(path, stat.S_IWRITE)
                func(path)

            shutil.rmtree(repo_path, onexc=on_rm_error)
            logger.info(f"Deleted local repository at {repo_path}")
        except Exception as e:
            logger.error(f"Failed to delete local repository at {repo_path}: {str(e)}")
            raise Exception(f"Failed to delete local repository: {str(e)}")
    else:
        logger.warning(f"Local repository at {repo_path} does not exist")

    try:
        gitea_repo_url = (
            f"{settings.GITEA_API_URL}/repos/{settings.GIT_OWNER}/{project_slug}"
        )
        headers = {"Authorization": f"token {settings.GITEA_TOKEN}"}
        response = requests.delete(gitea_repo_url, headers=headers, timeout=10)

        if response.status_code == 204:
            logger.info(f"Successfully deleted Gitea repository: {gitea_repo_url}")
        elif response.status_code == 404:
            logger.warning(f"Gitea repository not found: {gitea_repo_url}")
        else:
            logger.error(
                f"Failed to delete Gitea repository: {response.status_code} - {response.text}"
            )
            raise Exception(f"Failed to delete Gitea repository: {response.text}")
    except Exception as e:
        logger.error(f"Error deleting Gitea repository: {str(e)}")
        raise
