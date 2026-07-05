"""
Unit Tests — AuthDomainService (Domain Layer)
===============================================
Coverage target: 100% of AuthDomainService public methods.
Pattern: AAA (Arrange → Act → Assert)
SAD Reference: "Lógica de login y registro" (pág. 5), SAD flow pág. 9

All infrastructure (DB, Redis, bcrypt) is mocked.
JWT signing uses an ephemeral RSA key pair from conftest.py (RS256).
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import jwt as pyjwt
import pytest

from app.domain.auth_service import AuthDomainService, AuthError, RegistrationError, TokenPair
from app.domain.jwt_handler import JWTHandler
from app.domain.user import User, UserRole

TEST_ALGORITHM = "RS256"


def _make_user(
    email: str = "employee@fleet.com",
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


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.exists_by_email = AsyncMock(return_value=False)
    repo.find_by_email = AsyncMock(return_value=None)
    repo.save = AsyncMock(side_effect=lambda user: user)
    return repo


@pytest.fixture
def mock_hasher() -> MagicMock:
    hasher = MagicMock()
    hasher.hash = MagicMock(return_value="$bcrypt$hashed_password")
    hasher.verify = MagicMock(return_value=True)
    return hasher


@pytest.fixture
def jwt_handler(test_private_key, test_public_key) -> JWTHandler:
    return JWTHandler(
        private_key=test_private_key,
        public_key=test_public_key,
        algorithm=TEST_ALGORITHM,
        expiration_minutes=60,
    )


@pytest.fixture
def auth_service(mock_repo, mock_hasher, jwt_handler) -> AuthDomainService:
    return AuthDomainService(
        user_repository=mock_repo,
        password_hasher=mock_hasher,
        jwt_handler=jwt_handler,
    )


# =============================================================================
# AuthDomainService.register  (sin cambios — no toca JWT)
# =============================================================================


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_returns_user_entity(self, auth_service, mock_repo):
        mock_repo.exists_by_email.return_value = False
        result = await auth_service.register(email="new@fleet.com", plain_password="SecurePass1")
        assert isinstance(result, User)
        assert result.email == "new@fleet.com"

    @pytest.mark.asyncio
    async def test_register_assigns_default_empleado_role(self, auth_service, mock_repo):
        mock_repo.exists_by_email.return_value = False
        result = await auth_service.register(email="new@fleet.com", plain_password="SecurePass1")
        assert result.role == UserRole.EMPLEADO

    @pytest.mark.asyncio
    async def test_register_hashes_password_before_saving(self, auth_service, mock_repo, mock_hasher):
        plain = "SecurePass1"
        mock_repo.exists_by_email.return_value = False
        await auth_service.register(email="u@f.com", plain_password=plain)
        mock_hasher.hash.assert_called_once_with(plain)

    @pytest.mark.asyncio
    async def test_register_calls_repo_save(self, auth_service, mock_repo):
        mock_repo.exists_by_email.return_value = False
        await auth_service.register(email="u@f.com", plain_password="Pass1234")
        mock_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_normalizes_email_to_lowercase(self, auth_service, mock_repo):
        mock_repo.exists_by_email.return_value = False
        result = await auth_service.register(email="  UPPER@FLEET.COM  ", plain_password="Pass1234")
        assert result.email == "upper@fleet.com"

    @pytest.mark.asyncio
    async def test_register_raises_registration_error_if_email_exists(self, auth_service, mock_repo):
        mock_repo.exists_by_email.return_value = True
        with pytest.raises(RegistrationError) as exc_info:
            await auth_service.register(email="existing@fleet.com", plain_password="Pass1234")
        assert "already exists" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_register_does_not_call_save_when_email_exists(self, auth_service, mock_repo):
        mock_repo.exists_by_email.return_value = True
        with pytest.raises(RegistrationError):
            await auth_service.register(email="x@f.com", plain_password="Pass1")
        mock_repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_allows_explicit_role_assignment(self, auth_service, mock_repo):
        mock_repo.exists_by_email.return_value = False
        result = await auth_service.register(
            email="admin@fleet.com",
            plain_password="Admin1234",
            role=UserRole.ADMINISTRADOR,
        )
        assert result.role == UserRole.ADMINISTRADOR


# =============================================================================
# AuthDomainService.login
# =============================================================================


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_returns_jwt_string(self, auth_service, mock_repo, mock_hasher):
        user = _make_user(email="emp@fleet.com", is_active=True)
        mock_repo.find_by_email.return_value = user
        mock_hasher.verify.return_value = True
        result = await auth_service.login("emp@fleet.com", "password123")
        assert isinstance(result, str)
        assert result.count(".") == 2

    @pytest.mark.asyncio
    async def test_login_returns_token_pair_with_access_and_refresh_tokens(self, auth_service, mock_repo, mock_hasher):
        # Arrange
        user = _make_user(email="emp@fleet.com", is_active=True)
        mock_repo.find_by_email.return_value = user
        mock_hasher.verify.return_value = True
        # Act
        result = await auth_service.login("emp@fleet.com", "password123")
        # Assert
        assert isinstance(result, TokenPair)
        assert result.access_token.count(".") == 2
        assert result.refresh_token.count(".") == 2

    @pytest.mark.asyncio
    async def test_refresh_access_token_returns_new_access_token(self, auth_service, mock_repo, mock_hasher):
        # Arrange
        user = _make_user(email="emp@fleet.com", is_active=True)
        mock_repo.find_by_email.return_value = user
        mock_repo.find_by_id.return_value = user
        mock_hasher.verify.return_value = True
        tokens = await auth_service.login("emp@fleet.com", "password123")
        # Act
        refreshed = await auth_service.refresh_access_token(tokens.refresh_token)
        # Assert
        assert isinstance(refreshed, str)
        assert refreshed.count(".") == 2

    @pytest.mark.asyncio
    async def test_login_raises_auth_error_when_user_not_found(self, auth_service, mock_repo):
        mock_repo.find_by_email.return_value = None
        with pytest.raises(AuthError) as exc_info:
            await auth_service.login("ghost@fleet.com", "any_password")
        assert "Invalid email or password" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_login_raises_auth_error_when_password_wrong(self, auth_service, mock_repo, mock_hasher):
        user = _make_user(is_active=True)
        mock_repo.find_by_email.return_value = user
        mock_hasher.verify.return_value = False
        with pytest.raises(AuthError) as exc_info:
            await auth_service.login("employee@fleet.com", "wrong_pass")
        assert "Invalid email or password" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_login_raises_auth_error_when_user_is_inactive(self, auth_service, mock_repo, mock_hasher):
        user = _make_user(is_active=False)
        mock_repo.find_by_email.return_value = user
        mock_hasher.verify.return_value = True
        with pytest.raises(AuthError) as exc_info:
            await auth_service.login("employee@fleet.com", "correct_pass")
        assert "deactivated" in str(exc_info.value).lower() or "Invalid email or password" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_login_normalizes_email_before_lookup(self, auth_service, mock_repo, mock_hasher):
        user = _make_user(email="emp@fleet.com", is_active=True)
        mock_repo.find_by_email.return_value = user
        mock_hasher.verify.return_value = True
        await auth_service.login("  EMP@FLEET.COM  ", "pass")
        mock_repo.find_by_email.assert_called_once_with("emp@fleet.com")

    @pytest.mark.asyncio
    async def test_login_token_contains_user_id(self, auth_service, mock_repo, mock_hasher, test_public_key):
        # Arrange
        user = _make_user(email="emp@fleet.com", is_active=True)
        user_id = user.id
        mock_repo.find_by_email.return_value = user
        mock_hasher.verify.return_value = True
        # Act
        token = await auth_service.login("emp@fleet.com", "pass")
        # Assert — decode "from outside" using the PUBLIC key, like a real verifier
        payload = pyjwt.decode(token, test_public_key, algorithms=[TEST_ALGORITHM])
        assert payload["sub"] == user_id

    @pytest.mark.asyncio
    async def test_login_token_contains_correct_role(self, auth_service, mock_repo, mock_hasher, test_public_key):
        # Arrange
        user = _make_user(role=UserRole.ADMINISTRADOR, is_active=True)
        mock_repo.find_by_email.return_value = user
        mock_hasher.verify.return_value = True
        # Act
        token = await auth_service.login("emp@fleet.com", "pass")
        # Assert
        payload = pyjwt.decode(token, test_public_key, algorithms=[TEST_ALGORITHM])
        assert payload["role"] == "ADMINISTRADOR"
