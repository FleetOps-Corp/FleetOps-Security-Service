"""
Unit Tests — API Routes (API Layer)
====================================
SAD Reference: "POST /register · POST /login" (pág. 5 diagram — Auth Service <<API>>)
Coverage target: >=90% of routes.py

Strategy: build an isolated FastAPI app with only this router mounted,
override the get_db_session / get_redis dependencies (no real Postgres/Redis),
and monkeypatch _make_auth_service to inject a mocked AuthDomainService.
This keeps the test fully unit-level while still exercising the HTTP layer
(status codes, Pydantic validation, error mapping) end to end.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from auth_service.app.api import routes
from auth_service.app.domain.auth_service import AuthDomainService, AuthError, RegistrationError, TokenPair
from auth_service.app.domain.user import User, UserRole


def _make_user(
    email: str = "new@fleet.com",
    role: UserRole = UserRole.EMPLEADO,
    is_active: bool = True,
) -> User:
    return User(
        id="uuid-fixture",
        email=email,
        hashed_password="$bcrypt$hashed_password",
        role=role,
        is_active=is_active,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app_instance() -> FastAPI:
    app = FastAPI()
    app.include_router(routes.router)
    return app


@pytest.fixture
def mock_auth_service() -> AsyncMock:
    return AsyncMock(spec=AuthDomainService)


@pytest.fixture(autouse=True)
def override_infra_dependencies(app_instance):
    """Replace real DB/Redis dependencies with harmless fakes."""

    async def _fake_db_session():
        yield MagicMock()

    async def _fake_redis():
        yield MagicMock()

    app_instance.dependency_overrides[routes.get_db_session] = _fake_db_session
    app_instance.dependency_overrides[routes.get_redis] = _fake_redis
    yield
    app_instance.dependency_overrides.clear()


@pytest.fixture
def client(app_instance, mock_auth_service, monkeypatch):
    """AsyncClient wired to the isolated app, with the domain service mocked."""
    monkeypatch.setattr(
        routes,
        "_make_auth_service",
        lambda session, redis_client: mock_auth_service,
    )
    transport = ASGITransport(app=app_instance)
    return AsyncClient(transport=transport, base_url="http://test")


# =============================================================================
# POST /register
# =============================================================================


class TestRegisterEndpoint:
    @pytest.mark.asyncio
    async def test_register_success_returns_201(self, client, mock_auth_service):
        user = _make_user(email="new@fleet.com")
        mock_auth_service.register = AsyncMock(return_value=user)

        async with client as ac:
            response = await ac.post(
                "/register",
                json={"email": "new@fleet.com", "password": "SecurePass1"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "new@fleet.com"
        assert data["role"] == user.role.value
        assert data["is_active"] is True
        assert data["id"] == "uuid-fixture"

    @pytest.mark.asyncio
    async def test_register_duplicate_email_returns_409(self, client, mock_auth_service):
        mock_auth_service.register = AsyncMock(
            side_effect=RegistrationError("An account with email 'dup@fleet.com' already exists.")
        )

        async with client as ac:
            response = await ac.post(
                "/register",
                json={"email": "dup@fleet.com", "password": "SecurePass1"},
            )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_password_without_digit_returns_422(self, client, mock_auth_service):
        async with client as ac:
            response = await ac.post(
                "/register",
                json={"email": "new@fleet.com", "password": "NoDigitsHere"},
            )

        assert response.status_code == 422
        mock_auth_service.register.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_invalid_email_returns_422(self, client, mock_auth_service):
        async with client as ac:
            response = await ac.post(
                "/register",
                json={"email": "not-an-email", "password": "SecurePass1"},
            )

        assert response.status_code == 422
        mock_auth_service.register.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_password_too_short_returns_422(self, client, mock_auth_service):
        async with client as ac:
            response = await ac.post(
                "/register",
                json={"email": "new@fleet.com", "password": "P1"},
            )

        assert response.status_code == 422
        mock_auth_service.register.assert_not_called()


# =============================================================================
# POST /login
# =============================================================================


class TestLoginEndpoint:
    @pytest.mark.asyncio
    async def test_login_success_returns_token_pair(self, client, mock_auth_service):
        mock_auth_service.login = AsyncMock(
            return_value=TokenPair(access_token="access.tok.en", refresh_token="refresh.tok.en")
        )

        async with client as ac:
            response = await ac.post(
                "/login",
                json={"email": "emp@fleet.com", "password": "SecurePass1"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "access.tok.en"
        assert data["refresh_token"] == "refresh.tok.en"
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    @pytest.mark.asyncio
    async def test_login_invalid_credentials_returns_401(self, client, mock_auth_service):
        mock_auth_service.login = AsyncMock(side_effect=AuthError("Invalid email or password."))

        async with client as ac:
            response = await ac.post(
                "/login",
                json={"email": "ghost@fleet.com", "password": "wrongpass1"},
            )

        assert response.status_code == 401
        assert response.headers.get("www-authenticate") == "Bearer"
        assert "Invalid email or password" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_missing_fields_returns_422(self, client, mock_auth_service):
        async with client as ac:
            response = await ac.post("/login", json={"email": "emp@fleet.com"})

        assert response.status_code == 422
        mock_auth_service.login.assert_not_called()


# =============================================================================
# POST /refresh
# =============================================================================


class TestRefreshEndpoint:
    @pytest.mark.asyncio
    async def test_refresh_success_returns_new_access_token(self, client, mock_auth_service):
        mock_auth_service.refresh_access_token = AsyncMock(return_value="new.access.token")

        async with client as ac:
            response = await ac.post("/refresh", json={"refresh_token": "some.refresh.token"})

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "new.access.token"
        assert data["refresh_token"] == "some.refresh.token"
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_refresh_invalid_token_returns_401(self, client, mock_auth_service):
        mock_auth_service.refresh_access_token = AsyncMock(side_effect=AuthError("Invalid refresh token."))

        async with client as ac:
            response = await ac.post("/refresh", json={"refresh_token": "bad.token"})

        assert response.status_code == 401
        assert response.headers.get("www-authenticate") == "Bearer"

    @pytest.mark.asyncio
    async def test_refresh_missing_token_returns_422(self, client, mock_auth_service):
        async with client as ac:
            response = await ac.post("/refresh", json={})

        assert response.status_code == 422
        mock_auth_service.refresh_access_token.assert_not_called()


# =============================================================================
# Internal helpers: _make_auth_service / _BcryptHasher / get_redis
# =============================================================================


class TestInternalHelpers:
    def test_make_auth_service_wires_repository_hasher_and_jwt(self):
        session = MagicMock()
        redis_client = MagicMock()

        service = routes._make_auth_service(session, redis_client)

        assert isinstance(service, AuthDomainService)

    def test_bcrypt_hasher_hash_and_verify_roundtrip(self):
        hasher = routes._BcryptHasher()
        hashed = hasher.hash("SecurePass1")

        assert hashed != "SecurePass1"
        assert hasher.verify("SecurePass1", hashed) is True
        assert hasher.verify("WrongPass1", hashed) is False

    @pytest.mark.asyncio
    async def test_get_redis_yields_client_and_closes_on_exit(self, monkeypatch):
        fake_client = AsyncMock()
        fake_client.aclose = AsyncMock()
        fake_aioredis = MagicMock()
        fake_aioredis.from_url = MagicMock(return_value=fake_client)
        monkeypatch.setattr(routes, "aioredis", fake_aioredis)

        gen = routes.get_redis()
        client = await gen.__anext__()
        assert client is fake_client

        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()

        fake_client.aclose.assert_called_once()
