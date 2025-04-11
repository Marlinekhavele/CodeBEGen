import requests

from config import settings


def create_gitea_repo(project_name: str) -> str:
    """Creates a Gitea repository and returns its URL."""
    headers = {"Authorization": f"token {settings.GITEA_TOKEN}"}
    payload = {
        "name": project_name,
        "private": False,
        "description": f"Repository for {project_name}",
    }

    response = requests.post(
        f"{settings.GITEA_API_URL}/user/repos",
        json=payload,
        headers=headers,
        verify=False,
    )

    if response.status_code == 201:
        return response.json().get("html_url")
    else:
        raise Exception(f"Failed to create Gitea repo: {response.text}")


def get_repo_url(project_id: str) -> str:
    return f"https://159.203.105.4/git/CodeBEGen/{project_id}"
