"""
Role Service — RoleRepository (Infrastructure Layer)
=====================================================
SAD Reference: <<Infrastructure>> Role Service — "Repo roles · SQL queries · Alembic" (pág. 5)
               Proceso de validación pág. 10:
               "rolEnCache() → [miss] → consultarRol() [PostgreSQL]"
Pattern: Repository (GoF / DDD) + Cache-Aside (Redis)
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import redis.asyncio as aioredis
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.domain.role import Role, UserRoleAssignment
from app.infrastructure.models import RoleModel, User, UserRoleModel
from app.infrastructure.redis_client import role_cache_key

logger = logging.getLogger(__name__)


class RoleRepository:
    """
    Concrete implementation of the RoleRepository port.
    SAD pág. 10: rolEnCache → miss → consultarRol (PostgreSQL).
    """

    def __init__(self, session: AsyncSession, redis_client: aioredis.Redis) -> None:
        self._session = session
        self._redis = redis_client

    # -------------------------------------------------------------------------
    # ORM ↔ Domain mapping
    # -------------------------------------------------------------------------

    @staticmethod
    def _role_to_domain(model: RoleModel) -> Role:
        return Role(
            id=model.id,
            name=model.name,
            description=model.description or "",
            is_active=model.is_active,
            created_at=model.created_at,
        )

    @staticmethod
    def _assignment_to_domain(model: UserRoleModel) -> UserRoleAssignment:
        return UserRoleAssignment(
            id=model.id,
            user_id=model.user_id,
            role_id=model.role_id,
            role_name=model.role.name,
            assigned_at=model.assigned_at,
            assigned_by=model.assigned_by,
        )

    # -------------------------------------------------------------------------
    # Public interface
    # -------------------------------------------------------------------------

    async def find_role_by_name(self, name: str) -> Optional[Role]:
        stmt = select(RoleModel).where(RoleModel.name == name.upper())
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._role_to_domain(model) if model else None

    async def find_roles_by_user_id(self, user_id: str) -> list[UserRoleAssignment]:
        """
        SAD pág. 10 flow: checks Redis cache first (rolEnCache),
        then PostgreSQL (consultarRol) on miss.
        """
        cache_key = role_cache_key(user_id)

        # Step 1: Cache lookup (SAD pág. 10 — rolEnCache)
        try:
            cached = await self._redis.get(cache_key)
            if cached:
                logger.debug("Role cache HIT for user_id=%s", user_id)
                role_names: list[str] = json.loads(cached)
                # Reconstruct minimal assignments from cached role names
                return [
                    UserRoleAssignment(
                        id="cached",
                        user_id=user_id,
                        role_id="cached",
                        role_name=name,
                        assigned_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                        assigned_by=None,
                    )
                    for name in role_names
                ]
        except Exception as exc:
            logger.warning("Redis read error for roles (falling back): %s", exc)

        # Step 2: Database lookup (SAD pág. 10 — consultarRol)
        stmt = select(UserRoleModel).options(selectinload(UserRoleModel.role)).where(UserRoleModel.user_id == user_id)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        assignments = [self._assignment_to_domain(m) for m in models]

        # Step 3: Populate cache
        try:
            role_names_to_cache = [a.role_name for a in assignments]
            await self._redis.setex(
                cache_key,
                settings.redis_role_cache_ttl,
                json.dumps(role_names_to_cache),
            )
            logger.debug(
                "Cached roles for user_id=%s: %s (TTL=%ds)",
                user_id,
                role_names_to_cache,
                settings.redis_role_cache_ttl,
            )
        except Exception as exc:
            logger.warning("Redis write error for roles (non-fatal): %s", exc)

        return assignments

    async def save_role(self, role: Role) -> Role:
        model = RoleModel(
            id=role.id,
            name=role.name,
            description=role.description,
            is_active=role.is_active,
            created_at=role.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return role

    async def assign_role_to_user(self, assignment: UserRoleAssignment) -> UserRoleAssignment:
        model = UserRoleModel(
            id=assignment.id,
            user_id=assignment.user_id,
            role_id=assignment.role_id,
            assigned_at=assignment.assigned_at,
            assigned_by=assignment.assigned_by,
        )
        self._session.add(model)
        await self._session.flush()

        # Invalidate user role cache so next request gets fresh data
        try:
            await self._redis.delete(role_cache_key(assignment.user_id))
            logger.debug("Invalidated role cache for user_id=%s", assignment.user_id)
        except Exception as exc:
            logger.warning("Redis cache invalidation failed (non-fatal): %s", exc)

        return assignment

    async def remove_role_from_user(self, user_id: str, role_name: str) -> bool:
        # Find the role_id first
        role = await self.find_role_by_name(role_name)
        if role is None:
            return False

        stmt = delete(UserRoleModel).where(
            UserRoleModel.user_id == user_id,
            UserRoleModel.role_id == role.id,
        )
        result = await self._session.execute(stmt)

        # Invalidate cache on removal
        try:
            await self._redis.delete(role_cache_key(user_id))
        except Exception as exc:
            logger.warning("Redis cache invalidation failed (non-fatal): %s", exc)

        return result.rowcount > 0

    async def role_exists_by_name(self, name: str) -> bool:
        stmt = select(RoleModel.id).where(RoleModel.name == name.upper())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def update_user_current_role(self, user_id: str, role_id: str) -> bool:
        """
        Ejecuta un UPDATE directo en PostgreSQL para cambiar el rol actual del usuario.
        Utiliza la sesión compartida del repositorio.
        Retorna True si el usuario existía y fue modificado, False en caso contrario.
        """
        # 1. Usamos la sesión compartida: self._session
        stmt = update(User).where(User.id == user_id).values(role_id=role_id)

        result = await self._session.execute(stmt)

        # 2. Hacemos un flush para sincronizar el estado actual con Postgres
        # sin cerrar la transacción general (exactamente como lo haces en save_role)
        await self._session.flush()

        # Si rowcount > 0, significa que el usuario existía y se actualizó con éxito
        return result.rowcount > 0
