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

    # --- Redis ---
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    redis_session_cache_ttl: int = 3600

    # --- JWT (RSA asymmetric — SAD §7) ---
    jwt_private_key_path: str
    jwt_public_key_path: str
    jwt_algorithm: str = "RS256"
    jwt_expiration_minutes: int = 60

    # --- Server ---
    auth_service_port: int = 8001
    log_level: str = "INFO"
    app_env: str = "development"

    @property
    def jwt_private_key(self) -> str:
        return open(self.jwt_private_key_path, "r", encoding="utf-8").read()

    @property
    def jwt_public_key(self) -> str:
        return open(self.jwt_public_key_path, "r", encoding="utf-8").read()


settings = AuthSettings()  # type: ignore[call-arg]
