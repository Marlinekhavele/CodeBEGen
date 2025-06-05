import logging

import requests

from config import settings

logger = logging.getLogger(__name__)


def create_gitea_repo(project_name: str) -> str:
    """Creates a Gitea repository and returns its URL."""
    # Log configuration for debugging
    logger.info(f"Gitea API URL: {settings.GITEA_API_URL}")
    logger.info(f"Git Owner: {settings.GIT_OWNER}")
    logger.info(f"Creating repository: {project_name}")

    headers = {"Authorization": f"token {settings.GITEA_TOKEN}"}
    payload = {
        "name": project_name,
        "private": False,
        "description": f"Repository for {project_name}",
    }  # Construct the full URL
    api_url = f"{settings.GITEA_API_URL}/user/repos"
    logger.info(f"Making request to: {api_url}")

    try:
        response = requests.post(
            api_url,
            json=payload,
            headers=headers,
            verify=False,
            timeout=30,  # Add timeout
        )

        logger.info(f"Response status code: {response.status_code}")

        if response.status_code == 201:
            repo_data = response.json()
            html_url = repo_data.get("html_url")
            logger.info(f"Successfully created repository: {html_url}")
            return html_url
        elif response.status_code == 404:
            # Specific handling for 404 - likely server not running or wrong endpoint
            error_msg = f"Gitea server not found (404). Check if Gitea is running at {settings.GITEA_API_URL} and the API endpoint is correct."
            logger.error(error_msg)
            logger.error(
                f"Response content: {response.text[:500]}..."
            )  # Log first 500 chars
            raise Exception(error_msg)
        elif response.status_code == 401:
            error_msg = "Unauthorized (401). Check if GITEA_TOKEN is valid."
            logger.error(error_msg)
            raise Exception(error_msg)
        else:
            error_msg = f"Failed to create Gitea repo: {response.status_code} - {response.text[:500]}"
            logger.error(error_msg)
            raise Exception(error_msg)

    except requests.exceptions.RequestException as e:
        error_msg = f"Network error while creating Gitea repo: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


def get_repo_url(project_id: str) -> str:
    return f"{settings.CODE_BE_GEN_BASE_URL}/git/CodeBEGen/{project_id}"
