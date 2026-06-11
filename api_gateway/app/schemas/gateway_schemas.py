"""
API Gateway — Schemas / DTOs
==============================
SAD Reference: "DTOs para extraer solo la información necesaria" (§6)
Pattern: DTO (Data Transfer Object)

These schemas define the public contract of the API Gateway.
They enforce that only the minimum necessary data crosses the boundary.
"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response DTO."""
    status: str
    service: str
    version: str = "1.0.0"


class ErrorResponse(BaseModel):
    """Standardized error response DTO."""
    error: str
    detail: str
    path: str | None = None


class GatewayRouteInfo(BaseModel):
    """Route info DTO — used for documentation endpoint."""
    prefix: str
    upstream_url_key: str
    allowed_roles: list[str]
    description: str
    is_public: bool
