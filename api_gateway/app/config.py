"""
API Gateway — Configuration
============================
SAD Reference: Security Layer (pág. 5/6)
All configuration is externalized via environment variables (Rule R6).
No hardcoded secrets, ports, or environment-specific values.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    """
    Centralized configuration for the API Gateway.
    Values are loaded from environment variables (case-insensitive).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- JWT (SAD §7: confidentiality — session token) ---
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"

    # --- Internal service URLs (SAD §3: route dictionary) ---
    auth_service_url: str
    role_service_url: str

    # --- Downstream microservice URLs (placeholders — SAD §3) ---
    vehicles_service_url: str = "http://vehicles_service:8010"
    assignments_service_url: str = "http://assignments_service:8020"
    incidents_service_url: str = "http://incidents_service:8030"
    maintenance_service_url: str = "http://maintenance_service:8040"
    reports_service_url: str = "http://reports_service:8050"

    # --- Rate Limiting (SAD §6/7: efficiency tactic) ---
    gateway_rate_limit: int = 60  # requests per minute per client IP

    # --- Server ---
    gateway_port: int = 8000
    log_level: str = "INFO"
    app_env: str = "development"


# Singleton instance — imported by all modules
settings: GatewaySettings = GatewaySettings() # type: ignore[call-arg]
