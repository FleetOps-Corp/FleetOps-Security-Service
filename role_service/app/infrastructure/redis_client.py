"""
Role Service — Redis Client (Infrastructure Layer)
===================================================
SAD Reference: "Redis será empleado como sistema de almacenamiento temporal
               y cache para optimizar el rendimiento" (§9)
               "Los roles se consultan primero en Redis." (pág. 10 flow step 4)
Pattern: Cache-Aside (Redis)

[Archetype Convention Addition]
Cache invalidation strategy: TTL-based expiration (REDIS_ROLE_CACHE_TTL seconds).
Justified by: Redis cache-aside best practices; the SAD specifies caching but
does not define an invalidation strategy. TTL is the standard default.
"""

import logging
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

_ROLE_CACHE_KEY_PREFIX = "role:user:"


def role_cache_key(user_id: str) -> str:
    return f"{_ROLE_CACHE_KEY_PREFIX}{user_id}"


async def get_redis_client() -> AsyncGenerator[aioredis.Redis, None]:
    """FastAPI dependency yielding a Redis client."""
    client = aioredis.from_url(  # type: ignore[no-untyped-call]
        f"redis://{settings.redis_host}:{settings.redis_port}",
        password=settings.redis_password or None,
        encoding="utf-8",
        decode_responses=True,
    )
    try:
        yield client
    finally:
        await client.aclose()
