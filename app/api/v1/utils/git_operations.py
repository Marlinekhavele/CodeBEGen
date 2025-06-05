import json
import logging
import os
import shutil
import stat
import subprocess
from pathlib import Path

import requests

from config import BASE_DIR, settings

logger = logging.getLogger(__name__)

# Define the base directory for repositories
REPOS_DIR = Path("repos")
BASE_TEMPLATE_DIR = Path(BASE_DIR) / "project_template"


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
        # Create environment with SSL verification disabled
        env = os.environ.copy()
        env["GIT_SSL_NO_VERIFY"] = "true"

        # Special handling for commit commands to ensure proper escaping
        if (
            len(command) >= 3
            and command[0] == "git"
            and command[1] == "commit"
            and command[2] == "-m"
        ):
            # Use a more robust approach for commit messages
            commit_command = command[:3]  # ["git", "commit", "-m"]
            commit_message = command[3] if len(command) > 3 else ""

            # Ensure commit message is properly handled
            result = subprocess.run(
                commit_command + [commit_message],
                cwd=cwd,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
        else:
            result = subprocess.run(
                command, cwd=cwd, env=env, check=True, capture_output=True, text=True
            )

        output = result.stdout.strip()
        # Truncate long output for logging
        log_output = output[:500] + "..." if len(output) > 500 else output
        logger.info(f"Git command succeeded: {cmd_str}")
        logger.debug(f"Git command output: {log_output}")
        return output
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        logger.error(f"Git command failed: {cmd_str}")
        logger.error(f"Error details: {error_msg}")
        logger.error(f"Return code: {e.returncode}")

        # Special handling for common git errors
        if "nothing to commit" in error_msg:
            logger.info("Nothing to commit - working tree clean")
            # For commit operations, return the current HEAD commit hash
            if "commit" in command:
                try:
                    # Get the current commit hash
                    head_result = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=cwd,
                        env=env,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    return head_result.stdout.strip()
                except Exception:
                    # If we can't get the HEAD, just return a placeholder
                    return "HEAD"
            # For other operations, return empty string to indicate success with no output
            return ""

        # Handle case where a file is already staged but unchanged
        if "no changes added to commit" in error_msg:
            logger.info("No changes added to commit")
            # Similar to above, return current HEAD for commit operations
            if "commit" in command:
                try:
                    head_result = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=cwd,
                        env=env,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    return head_result.stdout.strip()
                except Exception:
                    return "HEAD"
            return ""

        # For other error cases, raise the exception with detailed error message
        raise Exception(f"Git command failed: {error_msg}")


def load_template_config(language):
    """Load the template config JSON from the language folder, or fallback to default behavior."""
    config_path = BASE_TEMPLATE_DIR / language / "template_config.json"
    if not config_path.exists():
        raise ValueError(f"Missing config for language: {language} at {config_path}")

    with open(config_path) as f:
        return json.load(f)


def clone_template_repo(project_dir, language):
    """Initialize a project from a multi-language-aware template folder."""
    template_dir = BASE_TEMPLATE_DIR / language
    if not template_dir.exists():
        raise ValueError(
            f"Template directory not found for language '{language}' at {template_dir}"
        )

    config = load_template_config(language)

    logger.info(f"Creating {language} project from template at {project_dir}")
    logger.info(f"Using template directory: {template_dir.absolute()}")

    # Copy directories
    for dir_name in config.get("copy_dirs", []):
        src_dir = template_dir / dir_name
        if not src_dir.exists():
            raise ValueError(f"Missing directory in template: {src_dir}")
        shutil.copytree(src_dir, project_dir / dir_name, dirs_exist_ok=True)

    # Copy files
    for file_name in config.get("copy_files", []):
        src_file = template_dir / file_name
        if src_file.exists():
            shutil.copy(src_file, project_dir / file_name)

    # Copy .gitignore if it exists in the template
    gitignore_src = template_dir / ".gitignore"
    if gitignore_src.exists():
        shutil.copy(gitignore_src, project_dir / ".gitignore")
    else:
        # Create default .gitignore if none exists in template
        with open(project_dir / ".gitignore", "w") as f:
            f.write(
                """# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Virtual Environment
venv/
env/
.env

# IDE
.vscode/
.idea/

# Logs
*.log

# DO NOT ignore database files and storage directory
!storage/
!storage/db/
!storage/db/db.sqlite
!storage/db/*.db

# Keep all migrations
!alembic/versions/*.py
"""
            )

    # Initialize git
    run_git_command(["git", "init"], cwd=project_dir)
    run_git_command(["git", "add", "."], cwd=project_dir)
    run_git_command(
        ["git", "commit", "-m", f"Initial commit for {language} template"],
        cwd=project_dir,
    )

    logger.info(f"Successfully initialized {language} project at {project_dir}")
    return f"{language.capitalize()} project initialized."


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

    # Add specific environment variables to disable SSL verification for Git
    env = os.environ.copy()
    env["GIT_SSL_NO_VERIFY"] = "true"

    try:
        # First set the branch to track the remote
        run_git_command(["git", "branch", "-M", branch], cwd=project_dir)
        logger.info(f"Set branch name to {branch}")

        # Create a custom subprocess call with the environment variables
        cmd = ["git", "push", "-u", "origin", branch]
        logger.info(f"Running command: {' '.join(cmd)}")

        result = subprocess.run(
            cmd, cwd=project_dir, env=env, check=True, capture_output=True, text=True
        )

        output = result.stdout.strip()
        logger.info(f"Push succeeded: {output[:200]}...")
        return output
    except subprocess.CalledProcessError as e:
        logger.error(f"Git push failed: {e.stderr}")
        # Continue anyway since we've created the local repository
        logger.warning("Continuing with local repository only")
        return "Push failed, but local repository was created"


def configure_git_for_project(project_dir):
    """Configure Git settings for the project to avoid credential prompts"""
    # Set Git to use credential helper with store option
    run_git_command(["git", "config", "credential.helper", "store"], cwd=project_dir)

    # Disable SSL verification
    gitea_domain = "localhost:3001"
    run_git_command(
        ["git", "config", f"http.{gitea_domain}.sslVerify", "false"], cwd=project_dir
    )

    # Always ensure user information is configured
    run_git_command(["git", "config", "user.name", "CodeBEGen Bot"], cwd=project_dir)
    run_git_command(
        ["git", "config", "user.email", "codebegen@example.com"], cwd=project_dir
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
