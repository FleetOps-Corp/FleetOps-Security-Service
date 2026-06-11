"""
Auth Service — UserRepository (Infrastructure Layer)
=====================================================
SAD Reference: <<Infrastructure>> Auth Service — "Repo usuarios · bcrypt · SQL" (pág. 5)
               Proceso de autenticación pág. 9:
               "usuarioEnCache() → [miss] → buscarUsuario() [PostgreSQL]"
Pattern: Repository (GoF / DDD) + Cache-Aside (Redis)

Implements the UserRepository protocol defined in the domain layer.
Translates between domain User entities and UserModel ORM objects.
Applies Redis cache-aside for login performance (SAD pág. 9).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
        return User(
            id=model.id,
            email=model.email,
            hashed_password=model.hashed_password,
            role=UserRole(model.role),
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
            "role": user.role.value,
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
            role=UserRole(data["role"]),
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
        SAD pág. 9: checks Redis cache first (usuarioEnCache),
        then PostgreSQL (buscarUsuario) on cache miss.
        """
        email_lower = email.lower()
        key = _cache_key(email_lower)

        # Step 1: Cache lookup (SAD pág. 9 — usuarioEnCache)
        try:
            cached = await self._redis.get(key)
            if cached:
                logger.debug("Cache HIT for user email: %s", email_lower)
                return self._from_cache_dict(json.loads(cached))
        except Exception as exc:
            logger.warning("Redis read error (falling back to DB): %s", exc)

        # Step 2: Database lookup (SAD pág. 9 — buscarUsuario)
        stmt = select(UserModel).where(UserModel.email == email_lower)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        user = self._to_domain(model)

        # Step 3: Populate cache (cache-aside write-through)
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
        model = UserModel(
            id=user.id,
            email=user.email,
            hashed_password=user.hashed_password,
            role=user.role.value,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        logger.info("Saved new user: id=%s email=%s role=%s", user.id, user.email, user.role.value)
        return user

    async def exists_by_email(self, email: str) -> bool:
        """Checks if an email is already registered (used during registration)."""
        email_lower = email.lower()
        stmt = select(UserModel.id).where(UserModel.email == email_lower)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
