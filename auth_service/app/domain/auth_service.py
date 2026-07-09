"""
Auth Service — AuthDomainService (Domain Layer)
================================================
SAD Reference: "Lógica de login y registro" (pág. 5 diagram)
               Flow: "validarCredenciales() → buscarUsuario() → retornarJWT()" (pág. 9)
Pattern: Domain Service (DDD)

Orchestrates the register and login use cases.
Depends on abstract interfaces (protocols), not concrete infrastructure classes,
keeping this layer fully testable without a real database or Redis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import jwt

from app.domain.jwt_handler import JWTHandler
from app.domain.user import User, UserRole

# ---------------------------------------------------------------------------
# Infrastructure protocols (ports — Hexagonal Architecture principle)
# Concrete adapters live in the infrastructure layer.
# ---------------------------------------------------------------------------


class UserRepository(Protocol):
    """Port: persistence of User entities."""

    async def find_by_email(self, email: str) -> User | None: ...
    async def find_by_id(self, user_id: str) -> User | None: ...
    async def save(self, user: User) -> User: ...
    async def exists_by_email(self, email: str) -> bool: ...


class PasswordHasher(Protocol):
    """Port: password hashing and verification."""

    def hash(self, plain_password: str) -> str: ...
    def verify(self, plain_password: str, hashed_password: str) -> bool: ...


# ---------------------------------------------------------------------------
# Result value objects
# ---------------------------------------------------------------------------


class AuthError(Exception):
    """Domain exception for authentication failures."""

    pass


class RegistrationError(Exception):
    """Domain exception for registration failures."""

    pass


@dataclass(frozen=True)
class TokenPair:
    """Value object representing access and refresh tokens issued together."""

    access_token: str
    refresh_token: str


# ---------------------------------------------------------------------------
# Domain Service
# ---------------------------------------------------------------------------


class AuthDomainService:
    """
    Domain service orchestrating user registration and login.
    SAD §3: "El servicio de autenticación valida las credenciales contra
            PostgreSQL. Si son válidas, genera un JWT."
    """

    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
        jwt_handler: JWTHandler,
    ) -> None:
        self._repo = user_repository
        self._hasher = password_hasher
        self._jwt = jwt_handler

    async def register(
        self,
        email: str,
        plain_password: str,
        role: UserRole | None = None,
    ) -> User:
        """
        Registers a new user in the system.

        SAD §3: "al momento del registro de un nuevo empleado no será
                asignado automáticamente el rol, será parte de la
                administración interna."
        → New users receive UserRole.EMPLEADO by default (team agreement).

        Args:
            email:          Validated email address.
            plain_password: Plain-text password (will be hashed here).
            role:           Override role — only used for seeding admin users.

        Returns:
            The persisted User entity.

        Raises:
            RegistrationError: if the email is already registered.
        """
        email_normalized = email.lower().strip()

        if await self._repo.exists_by_email(email_normalized):
            raise RegistrationError(f"An account with email '{email_normalized}' already exists.")

        hashed = self._hasher.hash(plain_password)
        user = User.create(
            email=email_normalized,
            hashed_password=hashed,
            role=role,
        )

        return await self._repo.save(user)

    async def login(self, email: str, plain_password: str) -> TokenPair:
        """
        Authenticates a user and returns a signed access/refresh token pair.

        SAD §3 flow (pág. 9):
          1. validarCredenciales() — check email + password
          2. buscarUsuario() — from PostgreSQL (via repo)
          3. retornarJWT() — if valid, generate token

        Args:
            email:          User's email address.
            plain_password: Plain-text password from the login request.

        Returns:
            TokenPair containing an access token and a refresh token.

        Raises:
            AuthError: if credentials are invalid or account is inactive.
        """
        email_normalized = email.lower().strip()
        user = await self._repo.find_by_email(email_normalized)

        if user is None:
            # Deliberately vague error — do not leak whether the email exists
            raise AuthError("Invalid email or password.")

        password_valid = user.is_password_correct(
            plain_password=plain_password,
            verify_fn=self._hasher.verify,
        )

        if not password_valid:
            raise AuthError("Invalid email or password.")

        if not user.is_active:  # pragma: no cover — defensive; User.is_password_correct already short-circuits on inactive
            raise AuthError("Account is deactivated. Contact your administrator.")

        access_token = self._jwt.create_token(
            user_id=user.id,
            role=user.role.name,
            email=user.email,
            token_type="access",
        )
        refresh_token = self._jwt.create_token(
            user_id=user.id,
            role=user.role.name,
            email=user.email,
            token_type="refresh",
        )

        return TokenPair(access_token=access_token, refresh_token=refresh_token)

    async def refresh_access_token(self, refresh_token: str) -> str:
        """Validates a refresh token and issues a new access token."""
        try:
            payload = self._jwt.decode_token(refresh_token)
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as exc:
            raise AuthError("Invalid refresh token.") from exc

        if payload.token_type != "refresh":
            raise AuthError("Invalid refresh token.")

        user = await self._repo.find_by_id(payload.user_id)
        if user is None:
            raise AuthError("Invalid refresh token.")

        if not user.is_active:
            raise AuthError("Account is deactivated. Contact your administrator.")

        return self._jwt.create_token(
            user_id=user.id,
            role=user.role.value,
            email=user.email,
            token_type="access",
        )
