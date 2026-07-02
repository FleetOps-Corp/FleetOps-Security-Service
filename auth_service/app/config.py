"""
Auth Service — Configuration
==============================
SAD Reference: Logic Layer — Auth Service (pág. 5)
All values are loaded from environment variables (Rule R6).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Database ---
    database_url: str
    database_url_sync: str

    # --- Redis (SAD pág. 9: session cache) ---
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    redis_session_cache_ttl: int = 3600

    # --- JWT (SAD §7) ---
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    # --- Server ---
    auth_service_port: int = 8001
    log_level: str = "INFO"
    app_env: str = "development"


settings = AuthSettings()  # type: ignore[call-arg]
