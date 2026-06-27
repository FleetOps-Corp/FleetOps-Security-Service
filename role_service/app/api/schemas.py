"""
Role Service — API Schemas / DTOs (API Layer)
==============================================
SAD Reference: "CRUD roles · Validación RBAC · DTOs · Verificación de roles"
               (pág. 5 — Role Service <<API>>)
"""

from pydantic import BaseModel, Field


class RoleValidationRequest(BaseModel):
    """
    Request to validate whether a user holds any of the required roles.
    SAD pág. 10 flow: sent by the API Gateway to verify permissions.
    """

    user_id: str = Field(..., description="User UUID from the JWT 'sub' claim")
    required_roles: list[str] = Field(
        ...,
        min_length=1,
        description="List of role names — access is granted if user holds any one of them",
    )


class RoleValidationResponse(BaseModel):
    """Response from the role validation endpoint."""

    authorized: bool
    user_id: str
    matched_role: str | None = None


class RoleAssignRequest(BaseModel):
    """
    Request to assign a role to a user.
    SAD §3: only administrators call this endpoint.
    """

    user_id: str = Field(..., description="Target user UUID")
    role_name: str = Field(..., description="Role to assign (e.g. EMPLEADO_MANTENIMIENTO)")
    assigned_by: str | None = Field(None, description="Admin user UUID performing the assignment")


class RoleAssignResponse(BaseModel):
    """Response after a successful role assignment."""

    assignment_id: str
    user_id: str
    role_name: str
    assigned_by: str | None


class UserRolesResponse(BaseModel):
    """Response listing all roles for a user."""

    user_id: str
    roles: list[str]


class RoleResponse(BaseModel):
    """Single role DTO."""

    id: str
    name: str
    description: str
    is_active: bool


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str = "1.0.0"


class ErrorResponse(BaseModel):
    error: str
    detail: str
