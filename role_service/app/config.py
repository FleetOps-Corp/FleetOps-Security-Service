"""Role Service — Configuration"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class RoleSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str
    database_url_sync: str

    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    redis_role_cache_ttl: int = 300

    role_service_port: int = 8002
    log_level: str = "INFO"
    app_env: str = "development"


settings = RoleSettings()  # type: ignore[call-arg]
