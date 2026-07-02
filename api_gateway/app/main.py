"""
API Gateway — Application Entry Point
=======================================
SAD Reference: Security Layer (pág. 5/6)
  "Aquí es donde se encuentra el Api gateway la cual contendrá las rutas
   y los roles permitidos a esas rutas, los CORS y se implementará rate
   limit para evitar el colapso del sistema ante múltiples peticiones
   simultáneas." (§6)

This module wires together:
  - CORS middleware (SAD §6)
  - Rate Limiting (SAD §6/7/8)
  - JWT extraction (SAD §3/7)
  - Route registry + RBAC policy (SAD §3/4)
  - Auth proxy routes (public)
  - Generic proxy routes (protected)
  - Health check endpoint (operational — Archetype Convention Addition,
    required for Docker Compose healthcheck per Rule R4)
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from app.routes.auth_routes import router as auth_router
from app.routes.proxy_routes import router as proxy_router
from app.schemas.gateway_schemas import HealthResponse

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="FleetOps — API Gateway",
    description=(
        "Security Layer: single entry point for the FleetOps distributed system. "
        "Handles JWT validation, RBAC enforcement, CORS, Rate Limiting, and routing "
        "to downstream microservices."
    ),
    version="1.0.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url="/redoc" if settings.app_env != "production" else None,
)

# ---------------------------------------------------------------------------
# Rate Limiting — attach limiter to app state (SAD §6/7: efficiency tactic)
# ---------------------------------------------------------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ---------------------------------------------------------------------------
# CORS — SAD §6: "los cors" en la capa de seguridad
# In production, restrict allow_origins to specific frontend domains.
# [Archetype Convention Addition] — externalize origins via env in production.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env == "development" else [],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# ---------------------------------------------------------------------------
# Routers
# Order matters: /auth (public) must be registered BEFORE the catch-all proxy.
# ---------------------------------------------------------------------------
app.include_router(auth_router)
app.include_router(proxy_router)


# ---------------------------------------------------------------------------
# Health check — [Archetype Convention Addition]
# Required for: docker-compose healthcheck (Rule R4), operational monitoring.
# Standard practice per Google SRE handbook and AWS health check conventions.
# ---------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse, tags=["Operations"])
async def health_check() -> HealthResponse:
    """
    Lightweight liveness probe.
    Returns 200 OK when the Gateway is running and accepting requests.
    """
    return HealthResponse(status="ok", service="api_gateway")


@app.on_event("startup")
async def on_startup() -> None:
    logger.info(
        "FleetOps API Gateway started | env=%s | port=%s",
        settings.app_env,
        settings.gateway_port,
    )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("FleetOps API Gateway shutting down")
