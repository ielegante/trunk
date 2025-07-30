import os
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Google OAuth Configuration
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_uri: str = os.getenv(
        "GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback"
    )

    # JWT Configuration
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "")
    if not jwt_secret_key:
        raise ValueError(
            "JWT_SECRET_KEY environment variable must be set. "
            "Generate a secure key using: openssl rand -hex 32"
        )
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_access_token_expire_minutes: int = int(
        os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )

    # Application Configuration
    app_name: str = os.getenv("APP_NAME", "Trunk Legal Git")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))

    # Database Configuration
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./trunk.db")

    # Cache Configuration (simplified - no Redis)
    cache_type: str = os.getenv("CACHE_TYPE", "memory")
    cache_max_size_mb: int = int(os.getenv("CACHE_MAX_SIZE_MB", "64"))

    # Git Server Configuration (simplified - embedded mode)
    git_server_type: str = os.getenv("GIT_SERVER_TYPE", "embedded")
    gitea_url: str = os.getenv("GITEA_URL", "")
    gitea_admin_token: Optional[str] = os.getenv("GITEA_ADMIN_TOKEN")

    class Config:
        env_file = ".env"


settings = Settings()
