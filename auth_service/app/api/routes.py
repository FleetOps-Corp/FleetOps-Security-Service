"""
Auth Service — API Routes (API Layer)
======================================
SAD Reference: "POST /register · POST /login" (pág. 5 diagram — Auth Service <<API>>)
               Proceso de autenticación (pág. 9)
Pattern: Controller (MVC) / Router (FastAPI)

Dependency injection wires the domain service with its infrastructure
adapters at the boundary — keeping the domain pure (SAD: GRASP §8).
"""

import logging
from collections.abc import AsyncGenerator
from typing import cast

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    ErrorResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.config import settings
from app.domain.auth_service import AuthDomainService, AuthError, RegistrationError
from app.domain.jwt_handler import JWTHandler
from app.infrastructure.database import get_db_session
from app.infrastructure.user_repository import UserRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Authentication"])

# ---------------------------------------------------------------------------
# Password hasher — passlib bcrypt adapter
# SAD §7: "Encriptar contraseña" — bcrypt
# ---------------------------------------------------------------------------
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class _BcryptHasher:
    """Concrete adapter for the PasswordHasher protocol."""
    def hash(self, plain_password: str) -> str:
        return cast(str, _pwd_context.hash(plain_password))

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        return cast(bool, _pwd_context.verify(plain_password, hashed_password))


_hasher = _BcryptHasher()
_jwt_handler = JWTHandler()


# ---------------------------------------------------------------------------
# Redis connection dependency
# [Archetype Convention Addition] — lazy Redis connection per request
# Justified by: redis-py best practice for async connection pooling
# ---------------------------------------------------------------------------
async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    client = aioredis.from_url( # type: ignore[no-untyped-call]
        f"redis://{settings.redis_host}:{settings.redis_port}",
        password=settings.redis_password or None,
        encoding="utf-8",
        decode_responses=True,
    )
    try:
        yield client
    finally:
        await client.aclose()


def _make_auth_service(
    session: AsyncSession,
    redis_client: aioredis.Redis,
) -> AuthDomainService:
    """
    Factory: wires domain service with concrete infrastructure adapters.
    SAD §8: GRASP — dependency injection keeps layers decoupled.
    """
    repo = UserRepository(session=session, redis_client=redis_client)
    return AuthDomainService(
        user_repository=repo,
        password_hasher=_hasher,
        jwt_handler=_jwt_handler,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}},
)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> UserResponse:
    """
    Registers a new FleetOps employee account.
    SAD §3: Role is NOT assigned automatically — admins assign roles later.
    New user defaults to role EMPLEADO.
    """
    auth_svc = _make_auth_service(session, redis_client)
    try:
        user = await auth_svc.register(
            email=body.email,
            plain_password=body.password,
        )
        logger.info("New user registered: id=%s email=%s", user.id, user.email)
        return UserResponse(
            id=user.id,
            email=user.email,
            role=user.role.value,
            is_active=user.is_active,
        )
    except RegistrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}},
)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> TokenResponse:
    """
    Authenticates a user and returns a signed JWT.
    SAD §3 flow (pág. 9): validarCredenciales → buscarUsuario → retornarJWT.
    Token expiration: 1 hour (SAD §7).
    """
    auth_svc = _make_auth_service(session, redis_client)
    try:
        token = await auth_svc.login(
            email=body.email,
            plain_password=body.password,
        )
        logger.info("Successful login for email: %s", body.email)
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=settings.jwt_expiration_minutes * 60,
        )
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )
