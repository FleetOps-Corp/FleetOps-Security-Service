"""
Auth Service — JWT Handler (Domain Layer)
==========================================
SAD Reference: "Servicio de negocio · JWT" (pág. 5 diagram)
               "JWT con tiempo válido de una hora. Sin actividad el token
               no se renueva." (§7)
Pattern: Domain Service

Responsible for creating and decoding JWT tokens.
No infrastructure dependencies — fully unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings


@dataclass(frozen=True)
class TokenPayload:
    """
    Value object representing the data encoded inside a JWT.
    SAD §7: sub (user_id), role, email + exp claim.
    """

    user_id: str
    role: str
    email: str
    expires_at: datetime
    token_type: str = "access"


class JWTHandler:
    """
    Domain service for JWT lifecycle management.
    SAD §7: confidentiality — session token with 1-hour expiration.
    """

    def __init__(
        self,
        private_key: str | None = None,
        public_key: str | None = None,
        algorithm: str | None = None,
        expiration_minutes: int | None = None,
        refresh_expiration_minutes: int | None = None,
    ) -> None:
        self._private_key = private_key or settings.jwt_private_key
        self._public_key = public_key or settings.jwt_public_key
        self._algorithm = algorithm or settings.jwt_algorithm
        self._expiry_minutes = expiration_minutes or settings.jwt_expiration_minutes
        self._refresh_expiry_minutes = refresh_expiration_minutes or settings.jwt_refresh_expiration_minutes

    def create_token(
        self,
        user_id: str,
        role: str,
        email: str,
        token_type: str = "access",
    ) -> str:
        """
        Creates a signed JWT for the given user.

        SAD §3 flow step 4: "Si son válidas, genera un JWT."
        SAD §7: Token expiration = 1 hour. No renewal without re-login.

        Args:
            user_id: User's UUID (stored as JWT 'sub' claim per RFC 7519).
            role:    User's RBAC role (custom claim).
            email:   User's email (custom claim for downstream traceability).

        Returns:
            Signed JWT string.
        """
        now = datetime.now(timezone.utc)
        expiry_minutes = self._refresh_expiry_minutes if token_type == "refresh" else self._expiry_minutes
        expires_at = now + timedelta(minutes=expiry_minutes)

        payload = {
            "sub": user_id,
            "role": role,
            "email": email,
            "iat": now,
            "exp": expires_at,
            "token_type": token_type,
        }

        # Firma con la clave PRIVADA
        return jwt.encode(payload, self._private_key, algorithm=self._algorithm)

    def decode_token(self, token: str) -> TokenPayload:
        """
        Decodes and validates a JWT, returning a typed TokenPayload.

        Args:
            token: Raw JWT string.

        Returns:
            TokenPayload with validated claims.

        Raises:
            jwt.ExpiredSignatureError: if token is expired.
            jwt.InvalidTokenError:     if token is invalid/tampered.
        """
        payload = jwt.decode(
            token,
            self._public_key,
            algorithms=[self._algorithm],
        )

        return TokenPayload(
            user_id=str(payload["sub"]),
            role=payload["role"],
            email=payload.get("email", ""),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            token_type=payload.get("token_type", "access"),
        )
