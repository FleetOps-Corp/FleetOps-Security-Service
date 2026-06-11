"""Role Service — Application Entry Point"""

import logging

from fastapi import FastAPI

from app.api.routes import router as roles_router
from app.api.schemas import HealthResponse
from app.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FleetOps — Role Service",
    description="Logic Layer: RBAC role validation, assignment, and management.",
    version="1.0.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url="/redoc" if settings.app_env != "production" else None,
)

app.include_router(roles_router)


@app.get("/health", response_model=HealthResponse, tags=["Operations"])
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="role_service")


@app.on_event("startup")
async def on_startup() -> None:
    logger.info(
        "FleetOps Role Service started | env=%s | port=%s",
        settings.app_env,
        settings.role_service_port,
    )
