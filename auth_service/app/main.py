"""
Auth Service — Application Entry Point
========================================
SAD Reference: Logic Layer — Auth Service (pág. 5)
Responsibilities: POST /register, POST /login, JWT generation
"""

import logging

from fastapi import FastAPI

from app.api.routes import router as auth_router
from app.api.schemas import HealthResponse
from app.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FleetOps — Auth Service",
    description="Logic Layer: user registration, login, and JWT generation.",
    version="1.0.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url="/redoc" if settings.app_env != "production" else None,
)

app.include_router(auth_router)


@app.get("/health", response_model=HealthResponse, tags=["Operations"])
async def health_check() -> HealthResponse:
    """Liveness probe for Docker Compose healthcheck."""
    return HealthResponse(status="ok", service="auth_service")


@app.on_event("startup")
async def on_startup() -> None:
    logger.info(
        "FleetOps Auth Service started | env=%s | port=%s",
        settings.app_env,
        settings.auth_service_port,
    )
