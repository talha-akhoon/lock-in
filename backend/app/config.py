from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LockIn"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://lockin:lockin@postgres:5432/lockin"
    # Long enough to satisfy HS256's recommended key length; still must be
    # replaced in any deployed environment.
    secret_key: str = "development-only-secret-key-replace-before-deploying"
    google_client_id: str = ""
    challenge_timezone: str = "Europe/London"
    frontend_dist: str = "../frontend/dist"
    secure_cookies: bool = False
    # Comma-separated Host values the MCP endpoint accepts, or * to skip the
    # DNS-rebinding check. Bearer auth is the real gate.
    mcp_allowed_hosts: str = "*"
    # Canonical public origin for OAuth issuer/resource metadata. Empty means
    # derive it from the incoming Host / X-Forwarded-* headers.
    public_origin: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
