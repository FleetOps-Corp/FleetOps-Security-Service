"""
API Gateway — JWT Middleware (Security Layer)
==============================================
SAD Reference: "Api Gateway valida el token, el rol y da acceso a la ruta" (§3, flow step 3)
               "JWT con tiempo válido de una hora" (§7)
Pattern: Middleware / Interceptor

Extracts and validates JWT from the Authorization header.
Decoded claims are injected into the request state for downstream use.
This middleware does NOT enforce RBAC — that is the RBACPolicy's responsibility.
"""

import logging
from typing import Any, Optional

import jwt
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


class JWTClaims:
    """
    Value object holding the decoded, validated claims from a JWT.
    Stored in request.state.jwt_claims after middleware processing.
    """
    def __init__(self, user_id: str, role: str, email: str) -> None:
        self.user_id = user_id
        self.role = role
        self.email = email

    def __repr__(self) -> str:
        return f"JWTClaims(user_id={self.user_id!r}, role={self.role!r})"


def decode_jwt(token: str) -> dict[str, Any]:
    """
    Decodes and validates a JWT token.

    Args:
        token: Raw JWT string (without "Bearer " prefix).

    Returns:
        Decoded payload dictionary.

    Raises:
        HTTPException 401 if the token is invalid, expired, or malformed.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT validation failed: token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        logger.warning("JWT validation failed: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def extract_claims(payload: dict[str, Any]) -> JWTClaims:
    """
    Extracts domain claims from the decoded JWT payload.

    Expected JWT structure (set by auth_service):
      {
        "sub": "<user_id>",
        "role": "<ROLE_STRING>",
        "email": "<user@example.com>",
        "exp": <unix_timestamp>
      }

    Raises:
        HTTPException 401 if required claims are missing.
    """
    user_id = payload.get("sub")
    role = payload.get("role")
    email = payload.get("email", "")

    if not user_id or not role:
        logger.warning("JWT missing required claims: sub or role")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing required claims.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return JWTClaims(user_id=str(user_id), role=role, email=email)


async def get_optional_jwt_claims(request: Request) -> Optional[JWTClaims]:
    """
    FastAPI dependency that extracts JWT claims from the request.
    Returns None if no token is present (for public routes).
    Raises HTTPException if a token is present but invalid.

    This is "optional" because public routes (/auth/*) carry no token.
    The RBAC layer decides whether a missing token is acceptable.
    """
    credentials: Optional[HTTPAuthorizationCredentials] = await _bearer_scheme(request)

    if credentials is None:
        return None

    payload = decode_jwt(credentials.credentials)
    claims = extract_claims(payload)

    # SAD §4: Accountability — log who is making requests (no sensitive data)
    logger.info(
        "Authenticated request | user_id=%s | role=%s | path=%s",
        claims.user_id,
        claims.role,
        request.url.path,
    )

    return claims
