from pathlib import Path
from typing import Optional

from decouple import config
from pydantic_settings import BaseSettings

# Use this to build paths inside the project
BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    # Debug mode
    DEBUG: bool = config("DEBUG", default=False, cast=bool)

    # Secret key for session
    SECRET_KEY: str = config("SECRET_KEY", default="your-secret-key-for-sessions")

    # Application port
    APP_PORT: int = config("APP_PORT", default=8000, cast=int)

    # Database configurations
    DB_HOST: str = config("DB_HOST", default="localhost")
    DB_PORT: int = config("DB_PORT", default=5432, cast=int)
    DB_USER: str = config("DB_USER", default="user")
    DB_PASSWORD: str = config("DB_PASSWORD", default="password")
    DB_NAME: str = config("DB_NAME", default="postgres")
    DB_TYPE: str = config("DB_TYPE", default="postgresql+asyncpg")

    # Optional database URL (if provided directly)
    database_url: Optional[str] = None

    # Gitea settings
    GITEA_API_URL: str = config(
        "GITEA_API_URL", default="https://gitea.example.com/api/v1"
    )
    GITEA_TOKEN: str = config("GITEA_TOKEN", default="")
    TEMPLATE_REPO_URL: str = config(
        "TEMPLATE_REPO_URL", default="https://gitea.example.com/template.git"
    )

    PROJECT_BASE: str = config("PROJECT_BASE", default="https://gitea.example.com/t")

    # Git user settings
    GIT_OWNER: str = config("GIT_OWNER", default="codebegen")
    GIT_USER_NAME: str = config("GIT_USER_NAME", default="Test User")
    GIT_USER_EMAIL: str = config("GIT_USER_EMAIL", default="test@example.com")

    ACCESS_TOKEN_EXPIRE_MINUTES: int = config(
        "ACCESS_TOKEN_EXPIRE_MINUTES", default=15, cast=int
    )
    JWT_REFRESH_EXPIRY_DAYS: int = config(
        "JWT_REFRESH_EXPIRY_DAYS", default=7, cast=int
    )

    ALGORITHM: str = config("ALGORITHM", default="HS256")

    # LLM settings
    ANTHROPIC_API_KEY: str = config("ANTHROPIC_API_KEY", default="")
    DEFAULT_LLM_PROVIDER: str = config(
        "DEFAULT_LLM_PROVIDER", default="anthropic/claude-3-sonnet-20240229"
    )
    LLM_MAX_TOKENS: int = config("LLM_MAX_TOKENS", default=4096, cast=int)
    LLM_TEMPERATURE: float = config("LLM_TEMPERATURE", default=0.7, cast=float)

    # Deployment settings for DevOps
    DEPLOYMENT_BASE_DIR: str = config("DEPLOYMENT_BASE_DIR", default="/var/www")
    SUBDOMAIN_BASE: str = config("SUBDOMAIN_BASE", default="codebegen")
    TEMP_CODE_DIR: str = config("TEMP_CODE_DIR", default="/tmp")
    GIT_SERVER_URL: str = config("GIT_SERVER_URL")
    RUNTIME_COMMAND: str = config("RUNTIME_COMMAND", default="python3")
    LOG_DIR: str = config("LOG_DIR", default="logs")

    REDIS_URL: str = config("REDIS_URL", default="redis://localhost:6379/1")
    CELERY_BROKER_URL: str = config(
        "CELERY_BROKER_URL", default="redis://localhost:6379/0"
    )
    CELERY_RESULT_BACKEND: str = config(
        "CELERY_RESULT_BACKEND", default="redis://localhost:6379/0"
    )

    # WebSocket settings
    REMOTE_WS_URL: str = config("REMOTE_WS_URL")
    MAX_RECONNECT_ATTEMPTS: int = config("MAX_RECONNECT_ATTEMPTS", default=5, cast=int)
    INITIAL_BACKOFF: int = config("INITIAL_BACKOFF", default=1, cast=int)
    MAX_BACKOFF: int = config("MAX_BACKOFF", default=60, cast=int)
    CONNECTION_TIMEOUT: int = config("CONNECTION_TIMEOUT", default=10, cast=int)
    MESSAGE_TIMEOUT: int = config("MESSAGE_TIMEOUT", default=30, cast=int)

    CONFIRM_PROJECT_DELETE_TOKEN: str = config(
        "CONFIRM_PROJECT_DELETE_TOKEN", default="CONFIRM_DELETE"
    )
    USE_SOFT_DELETE: bool = config("USE_SOFT_DELETE", default=True, cast=bool)

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
