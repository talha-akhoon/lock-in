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
    # Optional Web Push VAPID override. Empty means derive a stable pair from
    # SECRET_KEY so production needs no extra secret. Rotating SECRET_KEY
    # invalidates existing push subscriptions (and sessions).
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    # /mcp only. Per user after auth; per client IP for missing/invalid tokens.
    # 0 disables. Burst covers one multi-tool LLM turn; per_minute is the refill.
    mcp_rate_limit_per_minute: int = 60
    mcp_rate_limit_burst: int = 30
    mcp_anon_rate_limit_per_minute: int = 30
    mcp_anon_rate_limit_burst: int = 10

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
