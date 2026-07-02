"""
API Gateway — Rate Limiting (Security Layer)
=============================================
SAD Reference: "rate limit para evitar el colapso del sistema ante múltiples
               peticiones simultáneas" (§6)
               "límite de peticiones por segundo del mismo usuario" (§7/8)
Pattern: Throttling (Cloud Design Patterns)
Tactic: ISO/IEC 25010 — Eficiencia de desempeño, Utilización de recursos

Uses slowapi (limits wrapper for FastAPI) to enforce per-IP rate limits.
Limit value is externalized via environment variable GATEWAY_RATE_LIMIT.
"""

import logging

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

logger = logging.getLogger(__name__)

# Limiter instance — uses client IP as the key function
# SAD §7: "límite de peticiones por segundo del mismo usuario"
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.gateway_rate_limit}/minute"],
)


def rate_limit_exceeded_handler(request: Request, exc: Exception) -> Response:
    """
    Custom handler for rate limit violations.
    SAD §4: Protección — "bloqueo del acceso y reporta invalidez del rol para una acción"
    Returns HTTP 429 with a structured error body instead of the default plain text.
    """
    client_ip = get_remote_address(request)
    logger.warning(
        "Rate limit exceeded | ip=%s | path=%s | limit=%s",
        client_ip,
        request.url.path,
        settings.gateway_rate_limit,
    )
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "detail": f"Too many requests. Limit: {settings.gateway_rate_limit} requests/minute.",
            "path": str(request.url.path),
        },
    )
