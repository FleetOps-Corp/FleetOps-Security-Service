"""
conftest.py — API Gateway test configuration
==============================================
Sets all required environment variables BEFORE any app module is imported.
This is the correct pytest approach for services that use Pydantic Settings:
the production code remains clean (no Optional fields with None defaults for
truly required values), and tests supply safe test-only values.

[Archetype Convention Addition]
Justified by: pytest best practices for 12-factor apps (environment-based config).
"""

import os

# Set required env vars with safe test-only values before any import
os.environ.setdefault("JWT_SECRET_KEY", "test_secret_key_minimum_32_chars_long_ok")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("AUTH_SERVICE_URL", "http://auth_service_test:8001")
os.environ.setdefault("ROLE_SERVICE_URL", "http://role_service_test:8002")
os.environ.setdefault("GATEWAY_RATE_LIMIT", "60")
os.environ.setdefault("GATEWAY_PORT", "8000")
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("LOG_LEVEL", "WARNING")
