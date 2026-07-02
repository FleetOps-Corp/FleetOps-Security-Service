"""
Auth Service — UserRepository (Infrastructure Layer)
=====================================================
SAD Reference: <<Infrastructure>> Auth Service — "Repo usuarios · bcrypt · SQL" (pág. 5)
               Proceso de autenticación pág. 9:
               "usuarioEnCache() → [miss] → buscarUsuario() [PostgreSQL]"
Pattern: Repository (GoF / DDD) + Cache-Aside (Redis)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import settings
from app.domain.user import User, UserRole
from app.infrastructure.models import UserModel

logger = logging.getLogger(__name__)

_CACHE_KEY_PREFIX = "auth:user:email:"


def _cache_key(email: str) -> str:
    return f"{_CACHE_KEY_PREFIX}{email.lower()}"


class UserRepository:
    """
    Concrete implementation of the UserRepository port.
    SAD pág. 9 flow: checks Redis first, falls back to PostgreSQL.
    """

    def __init__(self, session: AsyncSession, redis_client: aioredis.Redis) -> None:
        self._session = session
        self._redis = redis_client

    # -------------------------------------------------------------------------
    # Internal helpers — ORM ↔ Domain mapping
    # -------------------------------------------------------------------------

    @staticmethod
    def _to_domain(model: UserModel) -> User:
        """Maps a UserModel (ORM) to a User (domain entity)."""

        role_name = model.role.name if model.role else "EMPLEADO"

        return User(
            id=model.id,
            email=model.email,
            hashed_password=model.hashed_password,
            # Convertimos el nombre del rol string al Enum de tu dominio
            role=UserRole(role_name),
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_cache_dict(user: User) -> dict[str, Any]:
        """Serializes a User to a dict for Redis storage."""
        return {
            "id": user.id,
            "email": user.email,
            "hashed_password": user.hashed_password,
            "role": user.role.value,  # Guardamos el string del enum en caché
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat(),
        }

    @staticmethod
    def _from_cache_dict(data: dict[str, Any]) -> User:
        """Deserializes a User from a Redis-cached dict."""
        from datetime import datetime

        return User(
            id=data["id"],
            email=data["email"],
            hashed_password=data["hashed_password"],
            role=UserRole(data["role"]),  # Mapeamos de vuelta al Enum de dominio
            is_active=bool(data["is_active"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )

    # -------------------------------------------------------------------------
    # Public interface (implements UserRepository protocol)
    # -------------------------------------------------------------------------

    async def find_by_email(self, email: str) -> Optional[User]:
        """
        Finds a user by email.
        SAD pág. 9: checks Redis cache first, then PostgreSQL on miss.
        """
        email_lower = email.lower()
        key = _cache_key(email_lower)

        try:
            cached = await self._redis.get(key)
            if cached:
                logger.debug("Cache HIT for user email: %s", email_lower)
                return self._from_cache_dict(json.loads(cached))
        except Exception as exc:
            logger.warning("Redis read error (falling back to DB): %s", exc)

        # Usamos joinedload(UserModel.role) para traernos el objeto del rol en una sola query
        stmt = select(UserModel).where(UserModel.email == email_lower).options(joinedload(UserModel.role))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        user = self._to_domain(model)

        try:
            await self._redis.setex(
                key,
                settings.redis_session_cache_ttl,
                json.dumps(self._to_cache_dict(user)),
            )
            logger.debug("Cached user: %s (TTL=%ds)", email_lower, settings.redis_session_cache_ttl)
        except Exception as exc:
            logger.warning("Redis write error (non-fatal): %s", exc)

        return user

    async def save(self, user: User) -> User:
        """Persists a new User entity to PostgreSQL."""

        # Diccionario estático sincronizado con Alembic
        role_mapping = {
            "EMPLEADO": "10131318-c79e-4691-91c3-30cd60056ab7",
            "EMPLEADO_MANTENIMIENTO": "2024b4f5-1445-4b08-8e81-d41c19b2650c",
            "EMPLEADO_INCIDENTES": "3034c5a6-2556-4c19-9f92-e52d20c3761d",
            "ADMINISTRADOR": "8db0189a-3505-41c2-ae29-45861557be8b",
        }

        assigned_role_id = role_mapping.get(user.role.value, "10131318-c79e-4691-91c3-30cd60056ab7")

        model = UserModel(
            id=user.id,
            email=user.email,
            hashed_password=user.hashed_password,
            role_id=assigned_role_id,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

        self._session.add(model)
        await self._session.flush()
        logger.info("Saved new user: id=%s email=%s role_id=%s", user.id, user.email, assigned_role_id)
        return user

    async def exists_by_email(self, email: str) -> bool:
        """Checks if an email is already registered."""
        email_lower = email.lower()
        stmt = select(UserModel.id).where(UserModel.email == email_lower)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
