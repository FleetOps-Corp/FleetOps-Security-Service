"""
Unit Tests — JWT Middleware (Security Layer)
=============================================
Coverage target: 100% of decode_jwt, extract_claims, get_optional_jwt_claims.
Pattern: AAA (Arrange → Act → Assert)
SAD Reference: "JWT con tiempo válido de una hora" (§7), JWT validation (§3/4)

All infrastructure is mocked — no real JWT secret required in tests.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException

from app.middleware.jwt_middleware import (
    JWTClaims,
    decode_jwt,
    extract_claims,
    get_optional_jwt_claims,
)

# =============================================================================
# Helpers
# =============================================================================

TEST_SECRET = "test_secret_key_for_unit_testing_only"
TEST_ALGORITHM = "HS256"


def _make_token(
    sub: str = "user-123",
    role: str = "EMPLEADO",
    email: str = "test@fleetops.com",
    expire_offset: int = 3600,
    secret: str = TEST_SECRET,
) -> str:
    """Creates a signed JWT for testing."""
    payload = {
        "sub": sub,
        "role": role,
        "email": email,
        "exp": int(time.time()) + expire_offset,
    }
    return jwt.encode(payload, secret, algorithm=TEST_ALGORITHM)


# =============================================================================
# JWTClaims value object
# =============================================================================

class TestJWTClaims:

    def test_claims_stores_all_fields(self):
        # Arrange & Act
        claims = JWTClaims(user_id="u1", role="ADMINISTRADOR", email="a@b.com")
        # Assert
        assert claims.user_id == "u1"
        assert claims.role == "ADMINISTRADOR"
        assert claims.email == "a@b.com"

    def test_claims_repr_does_not_expose_email(self):
        # Arrange — repr should not expose PII beyond user_id and role
        claims = JWTClaims(user_id="u1", role="EMPLEADO", email="private@example.com")
        # Act
        rep = repr(claims)
        # Assert
        assert "private@example.com" not in rep


# =============================================================================
# decode_jwt
# =============================================================================

class TestDecodeJWT:

    def test_valid_token_returns_payload(self):
        # Arrange
        token = _make_token()
        # Act
        with patch("app.middleware.jwt_middleware.settings") as mock_settings:
            mock_settings.jwt_secret_key = TEST_SECRET
            mock_settings.jwt_algorithm = TEST_ALGORITHM
            payload = decode_jwt(token)
        # Assert
        assert payload["sub"] == "user-123"
        assert payload["role"] == "EMPLEADO"

    def test_expired_token_raises_401(self):
        # Arrange — token expired 1 second ago
        token = _make_token(expire_offset=-1)
        # Act & Assert
        with patch("app.middleware.jwt_middleware.settings") as mock_settings:
            mock_settings.jwt_secret_key = TEST_SECRET
            mock_settings.jwt_algorithm = TEST_ALGORITHM
            with pytest.raises(HTTPException) as exc_info:
                decode_jwt(token)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_tampered_token_raises_401(self):
        # Arrange — sign with a different secret
        token = _make_token(secret="wrong_secret")
        # Act & Assert
        with patch("app.middleware.jwt_middleware.settings") as mock_settings:
            mock_settings.jwt_secret_key = TEST_SECRET
            mock_settings.jwt_algorithm = TEST_ALGORITHM
            with pytest.raises(HTTPException) as exc_info:
                decode_jwt(token)
        assert exc_info.value.status_code == 401

    def test_malformed_token_raises_401(self):
        # Arrange
        token = "not.a.valid.jwt"
        # Act & Assert
        with patch("app.middleware.jwt_middleware.settings") as mock_settings:
            mock_settings.jwt_secret_key = TEST_SECRET
            mock_settings.jwt_algorithm = TEST_ALGORITHM
            with pytest.raises(HTTPException) as exc_info:
                decode_jwt(token)
        assert exc_info.value.status_code == 401

    def test_empty_token_raises_401(self):
        # Arrange
        token = ""
        # Act & Assert
        with patch("app.middleware.jwt_middleware.settings") as mock_settings:
            mock_settings.jwt_secret_key = TEST_SECRET
            mock_settings.jwt_algorithm = TEST_ALGORITHM
            with pytest.raises(HTTPException) as exc_info:
                decode_jwt(token)
        assert exc_info.value.status_code == 401


# =============================================================================
# extract_claims
# =============================================================================

class TestExtractClaims:

    def test_valid_payload_returns_claims(self):
        # Arrange
        payload = {
            "sub": "user-456",
            "role": "ADMINISTRADOR",
            "email": "admin@fleetops.com",
        }
        # Act
        claims = extract_claims(payload)
        # Assert
        assert claims.user_id == "user-456"
        assert claims.role == "ADMINISTRADOR"
        assert claims.email == "admin@fleetops.com"

    def test_payload_without_sub_raises_401(self):
        # Arrange
        payload = {"role": "EMPLEADO", "email": "x@y.com"}
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            extract_claims(payload)
        assert exc_info.value.status_code == 401

    def test_payload_without_role_raises_401(self):
        # Arrange
        payload = {"sub": "user-789", "email": "x@y.com"}
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            extract_claims(payload)
        assert exc_info.value.status_code == 401

    def test_payload_without_email_uses_empty_string(self):
        # Arrange — email is optional
        payload = {"sub": "user-111", "role": "EMPLEADO"}
        # Act
        claims = extract_claims(payload)
        # Assert
        assert claims.email == ""

    def test_sub_is_converted_to_string(self):
        # Arrange — sub could be an integer in some JWT implementations
        payload = {"sub": 42, "role": "EMPLEADO", "email": "t@t.com"}
        # Act
        claims = extract_claims(payload)
        # Assert
        assert claims.user_id == "42"
        assert isinstance(claims.user_id, str)


# =============================================================================
# get_optional_jwt_claims (async dependency)
# =============================================================================

class TestGetOptionalJWTClaims:

    @pytest.mark.asyncio
    async def test_returns_none_when_no_authorization_header(self):
        # Arrange — mock request with no bearer token
        mock_request = MagicMock()

        with patch(
            "app.middleware.jwt_middleware._bearer_scheme",
            new_callable=AsyncMock,
            return_value=None,
        ):
            # Act
            result = await get_optional_jwt_claims(mock_request)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_claims_for_valid_token(self):
        # Arrange
        token = _make_token(sub="user-999", role="ADMINISTRADOR")
        mock_credentials = MagicMock()
        mock_credentials.credentials = token
        mock_request = MagicMock()
        mock_request.url.path = "/vehiculos/list"

        with patch(
            "app.middleware.jwt_middleware._bearer_scheme",
            new_callable=AsyncMock,
            return_value=mock_credentials,
        ), patch("app.middleware.jwt_middleware.settings") as mock_settings:
            mock_settings.jwt_secret_key = TEST_SECRET
            mock_settings.jwt_algorithm = TEST_ALGORITHM
            # Act
            result = await get_optional_jwt_claims(mock_request)

        # Assert
        assert result is not None
        assert result.user_id == "user-999"
        assert result.role == "ADMINISTRADOR"

    @pytest.mark.asyncio
    async def test_raises_401_for_expired_token(self):
        # Arrange
        expired_token = _make_token(expire_offset=-1)
        mock_credentials = MagicMock()
        mock_credentials.credentials = expired_token
        mock_request = MagicMock()
        mock_request.url.path = "/vehiculos"

        with patch(
            "app.middleware.jwt_middleware._bearer_scheme",
            new_callable=AsyncMock,
            return_value=mock_credentials,
        ), patch("app.middleware.jwt_middleware.settings") as mock_settings:
            mock_settings.jwt_secret_key = TEST_SECRET
            mock_settings.jwt_algorithm = TEST_ALGORITHM
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await get_optional_jwt_claims(mock_request)

        assert exc_info.value.status_code == 401
