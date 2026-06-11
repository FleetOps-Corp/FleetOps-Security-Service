"""
Unit Tests — JWTHandler (Domain Layer)
========================================
Coverage target: 100% of JWTHandler public methods.
Pattern: AAA (Arrange → Act → Assert)
SAD Reference: "JWT con tiempo válido de una hora" (§7)

Uses an injected test secret — no real settings loaded.
"""

import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.domain.jwt_handler import JWTHandler, TokenPayload

TEST_SECRET = "unit_test_secret_not_for_production"
TEST_ALGORITHM = "HS256"
TEST_EXPIRY_MINUTES = 60


@pytest.fixture
def handler() -> JWTHandler:
    """A JWTHandler instance with injected test configuration."""
    return JWTHandler(
        secret_key=TEST_SECRET,
        algorithm=TEST_ALGORITHM,
        expiration_minutes=TEST_EXPIRY_MINUTES,
    )


# =============================================================================
# JWTHandler.create_token
# =============================================================================

class TestCreateToken:

    def test_create_token_returns_non_empty_string(self, handler: JWTHandler):
        # Act
        token = handler.create_token("u-1", "EMPLEADO", "e@f.com")
        # Assert
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_has_three_jwt_segments(self, handler: JWTHandler):
        # JWT format: header.payload.signature
        token = handler.create_token("u-1", "EMPLEADO", "e@f.com")
        assert token.count(".") == 2

    def test_token_contains_correct_sub_claim(self, handler: JWTHandler):
        # Arrange
        user_id = "user-uuid-123"
        # Act
        token = handler.create_token(user_id, "EMPLEADO", "e@f.com")
        payload = jwt.decode(token, TEST_SECRET, algorithms=[TEST_ALGORITHM])
        # Assert
        assert payload["sub"] == user_id

    def test_token_contains_correct_role_claim(self, handler: JWTHandler):
        token = handler.create_token("u-1", "ADMINISTRADOR", "a@f.com")
        payload = jwt.decode(token, TEST_SECRET, algorithms=[TEST_ALGORITHM])
        assert payload["role"] == "ADMINISTRADOR"

    def test_token_contains_correct_email_claim(self, handler: JWTHandler):
        email = "fleet@ops.com"
        token = handler.create_token("u-1", "EMPLEADO", email)
        payload = jwt.decode(token, TEST_SECRET, algorithms=[TEST_ALGORITHM])
        assert payload["email"] == email

    def test_token_expiry_is_approximately_one_hour(self, handler: JWTHandler):
        # Arrange
        before = time.time()
        # Act
        token = handler.create_token("u-1", "EMPLEADO", "e@f.com")
        payload = jwt.decode(token, TEST_SECRET, algorithms=[TEST_ALGORITHM])
        # Assert — expiry should be ~3600 seconds from now (±5s tolerance)
        exp = payload["exp"]
        delta = exp - before
        assert 3595 <= delta <= 3605

    def test_token_contains_iat_claim(self, handler: JWTHandler):
        token = handler.create_token("u-1", "EMPLEADO", "e@f.com")
        payload = jwt.decode(token, TEST_SECRET, algorithms=[TEST_ALGORITHM])
        assert "iat" in payload

    def test_different_users_produce_different_tokens(self, handler: JWTHandler):
        token_a = handler.create_token("user-A", "EMPLEADO", "a@f.com")
        token_b = handler.create_token("user-B", "EMPLEADO", "b@f.com")
        assert token_a != token_b


# =============================================================================
# JWTHandler.decode_token
# =============================================================================

class TestDecodeToken:

    def _make_raw_token(
        self,
        sub: str = "u-1",
        role: str = "EMPLEADO",
        email: str = "e@f.com",
        expire_offset_seconds: int = 3600,
    ) -> str:
        payload = {
            "sub": sub,
            "role": role,
            "email": email,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(seconds=expire_offset_seconds),
        }
        return jwt.encode(payload, TEST_SECRET, algorithm=TEST_ALGORITHM)

    def test_decode_valid_token_returns_token_payload(self, handler: JWTHandler):
        # Arrange
        token = self._make_raw_token(sub="user-42", role="ADMINISTRADOR")
        # Act
        result = handler.decode_token(token)
        # Assert
        assert isinstance(result, TokenPayload)
        assert result.user_id == "user-42"
        assert result.role == "ADMINISTRADOR"

    def test_decode_returns_correct_user_id(self, handler: JWTHandler):
        token = self._make_raw_token(sub="uuid-999")
        result = handler.decode_token(token)
        assert result.user_id == "uuid-999"

    def test_decode_returns_correct_role(self, handler: JWTHandler):
        token = self._make_raw_token(role="EMPLEADO_MANTENIMIENTO")
        result = handler.decode_token(token)
        assert result.role == "EMPLEADO_MANTENIMIENTO"

    def test_decode_returns_correct_email(self, handler: JWTHandler):
        token = self._make_raw_token(email="ops@fleet.com")
        result = handler.decode_token(token)
        assert result.email == "ops@fleet.com"

    def test_decode_returns_expires_at_as_datetime(self, handler: JWTHandler):
        token = self._make_raw_token()
        result = handler.decode_token(token)
        assert isinstance(result.expires_at, datetime)
        assert result.expires_at.tzinfo is not None

    def test_decode_expired_token_raises_expired_signature_error(
        self, handler: JWTHandler
    ):
        # Arrange — token expired 1 second ago
        token = self._make_raw_token(expire_offset_seconds=-1)
        # Act & Assert
        with pytest.raises(jwt.ExpiredSignatureError):
            handler.decode_token(token)

    def test_decode_tampered_token_raises_invalid_token_error(
        self, handler: JWTHandler
    ):
        # Arrange — signed with wrong secret
        token = jwt.encode(
            {"sub": "u", "role": "EMPLEADO", "exp": time.time() + 3600},
            "wrong_secret",
            algorithm=TEST_ALGORITHM,
        )
        # Act & Assert
        with pytest.raises(jwt.InvalidTokenError):
            handler.decode_token(token)

    def test_create_and_decode_roundtrip(self, handler: JWTHandler):
        # Arrange
        user_id = "round-trip-user"
        role = "EMPLEADO_INCIDENTES"
        email = "incidents@fleet.com"
        # Act
        token = handler.create_token(user_id, role, email)
        decoded = handler.decode_token(token)
        # Assert
        assert decoded.user_id == user_id
        assert decoded.role == role
        assert decoded.email == email
