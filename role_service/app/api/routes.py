"""
Role Service — API Routes (API Layer)
======================================
SAD Reference: "CRUD roles · Validación RBAC" (pág. 5 diagram)
               Proceso de validación y redirección (pág. 10)
Endpoints:
  POST /roles/validate      — called by API Gateway to verify user permissions
  POST /roles/assign        — admin assigns a role to a user
  DELETE /roles/remove      — admin removes a role from a user
  GET  /roles/user/{user_id} — get all roles for a user
"""

import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    RoleAssignRequest,
    RoleAssignResponse,
    RoleValidationRequest,
    RoleValidationResponse,
    UserRolesResponse,
)
from app.domain.role_service import RoleAssignmentError, RoleDomainService, RoleNotFoundError
from app.infrastructure.database import get_db_session
from app.infrastructure.redis_client import get_redis_client
from app.infrastructure.role_repository import RoleRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/roles", tags=["Roles"])


def _make_role_service(
    session: AsyncSession,
    redis_client: aioredis.Redis,
) -> RoleDomainService:
    """Factory: wires domain service with repository adapter."""
    repo = RoleRepository(session=session, redis_client=redis_client)
    return RoleDomainService(role_repository=repo)


@router.post(
    "/validate",
    response_model=RoleValidationResponse,
    summary="Validate user role (called by API Gateway)",
)
async def validate_role(
    body: RoleValidationRequest,
    session: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> RoleValidationResponse:
    """
    SAD pág. 10 flow: API Gateway calls this to verify permissions.
    Returns authorized=True if user holds any of the required roles.
    Roles are checked in Redis first (rolEnCache), then PostgreSQL (consultarRol).
    """
    svc = _make_role_service(session, redis_client)
    user_roles = await svc.get_user_roles(body.user_id)
    required_upper = {r.upper() for r in body.required_roles}
    matched = set(user_roles) & required_upper

    authorized = bool(matched)
    matched_role = next(iter(matched), None) if matched else None

    logger.info(
        "Role validation | user_id=%s | required=%s | authorized=%s",
        body.user_id,
        body.required_roles,
        authorized,
    )
    return RoleValidationResponse(
        authorized=authorized,
        user_id=body.user_id,
        matched_role=matched_role,
    )


@router.post(
    "/assign",
    response_model=RoleAssignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign a role to a user (ADMINISTRADOR only)",
)
async def assign_role(
    body: RoleAssignRequest,
    session: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> RoleAssignResponse:
    """
    SAD §3: "la administración del sistema" assigns roles.
    Note: caller must ensure request comes from an ADMINISTRADOR
    (enforced at the Gateway RBAC layer before reaching this endpoint).
    """
    svc = _make_role_service(session, redis_client)
    try:
        assignment = await svc.assign_role(
            user_id=body.user_id,
            role_name=body.role_name,
            assigned_by=body.assigned_by,
        )
        logger.info(
            "Role assigned | user_id=%s | role=%s | by=%s",
            body.user_id,
            body.role_name,
            body.assigned_by,
        )
        return RoleAssignResponse(
            assignment_id=assignment.id,
            user_id=assignment.user_id,
            role_name=assignment.role_name,
            assigned_by=assignment.assigned_by,
        )
    except RoleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RoleAssignmentError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.delete(
    "/remove",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a role from a user (ADMINISTRADOR only)",
)
async def remove_role(
    user_id: str,
    role_name: str,
    session: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> None:
    svc = _make_role_service(session, redis_client)
    try:
        await svc.remove_role(user_id=user_id, role_name=role_name)
    except RoleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/user/{user_id}",
    response_model=UserRolesResponse,
    summary="Get all roles for a user",
)
async def get_user_roles(
    user_id: str,
    session: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> UserRolesResponse:
    """Returns the complete role list for a given user."""
    svc = _make_role_service(session, redis_client)
    roles = await svc.get_user_roles(user_id)
    return UserRolesResponse(user_id=user_id, roles=roles)
