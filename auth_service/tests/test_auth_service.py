"""
Unit Tests — AuthDomainService (Domain Layer)
===============================================
Coverage target: 100% of AuthDomainService public methods.
Pattern: AAA (Arrange → Act → Assert)
SAD Reference: "Lógica de login y registro" (pág. 5), SAD flow pág. 9

All infrastructure (DB, Redis, bcrypt) is mocked.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.auth_service import AuthDomainService, AuthError, RegistrationError
from app.domain.jwt_handler import JWTHandler
from app.domain.user import User, UserRole

# =============================================================================
# Fixtures
# =============================================================================

TEST_SECRET = "test_secret"
TEST_ALGORITHM = "HS256"


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
def jwt_handler() -> JWTHandler:
    return JWTHandler(
        secret_key=TEST_SECRET,
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
# AuthDomainService.register
# =============================================================================

class TestRegister:

    @pytest.mark.asyncio
    async def test_register_returns_user_entity(self, auth_service, mock_repo):
        # Arrange
        mock_repo.exists_by_email.return_value = False
        # Act
        result = await auth_service.register(
            email="new@fleet.com",
            plain_password="SecurePass1",
        )
        # Assert
        assert isinstance(result, User)
        assert result.email == "new@fleet.com"

    @pytest.mark.asyncio
    async def test_register_assigns_default_empleado_role(self, auth_service, mock_repo):
        # SAD §3: new users default to EMPLEADO
        mock_repo.exists_by_email.return_value = False
        result = await auth_service.register(
            email="new@fleet.com",
            plain_password="SecurePass1",
        )
        assert result.role == UserRole.EMPLEADO

    @pytest.mark.asyncio
    async def test_register_hashes_password_before_saving(
        self, auth_service, mock_repo, mock_hasher
    ):
        # Arrange
        plain = "SecurePass1"
        mock_repo.exists_by_email.return_value = False
        # Act
        await auth_service.register(email="u@f.com", plain_password=plain)
        # Assert — hasher.hash must be called with the plain password
        mock_hasher.hash.assert_called_once_with(plain)

    @pytest.mark.asyncio
    async def test_register_calls_repo_save(self, auth_service, mock_repo):
        # Arrange
        mock_repo.exists_by_email.return_value = False
        # Act
        await auth_service.register(email="u@f.com", plain_password="Pass1234")
        # Assert
        mock_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_normalizes_email_to_lowercase(
        self, auth_service, mock_repo
    ):
        # Arrange
        mock_repo.exists_by_email.return_value = False
        # Act
        result = await auth_service.register(
            email="  UPPER@FLEET.COM  ",
            plain_password="Pass1234",
        )
        # Assert
        assert result.email == "upper@fleet.com"

    @pytest.mark.asyncio
    async def test_register_raises_registration_error_if_email_exists(
        self, auth_service, mock_repo
    ):
        # Arrange
        mock_repo.exists_by_email.return_value = True
        # Act & Assert
        with pytest.raises(RegistrationError) as exc_info:
            await auth_service.register(
                email="existing@fleet.com",
                plain_password="Pass1234",
            )
        assert "already exists" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_register_does_not_call_save_when_email_exists(
        self, auth_service, mock_repo
    ):
        # Arrange
        mock_repo.exists_by_email.return_value = True
        # Act
        with pytest.raises(RegistrationError):
            await auth_service.register(email="x@f.com", plain_password="Pass1")
        # Assert — save must NOT be called on conflict
        mock_repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_allows_explicit_role_assignment(
        self, auth_service, mock_repo
    ):
        # Arrange — used for admin seeding
        mock_repo.exists_by_email.return_value = False
        # Act
        result = await auth_service.register(
            email="admin@fleet.com",
            plain_password="Admin1234",
            role=UserRole.ADMINISTRADOR,
        )
        # Assert
        assert result.role == UserRole.ADMINISTRADOR


# =============================================================================
# AuthDomainService.login
# =============================================================================

class TestLogin:

    @pytest.mark.asyncio
    async def test_login_returns_jwt_string(
        self, auth_service, mock_repo, mock_hasher
    ):
        # Arrange
        user = _make_user(email="emp@fleet.com", is_active=True)
        mock_repo.find_by_email.return_value = user
        mock_hasher.verify.return_value = True
        # Act
        result = await auth_service.login("emp@fleet.com", "password123")
        # Assert
        assert isinstance(result, str)
        assert result.count(".") == 2  # valid JWT has 3 segments

    @pytest.mark.asyncio
    async def test_login_raises_auth_error_when_user_not_found(
        self, auth_service, mock_repo
    ):
        # Arrange
        mock_repo.find_by_email.return_value = None
        # Act & Assert
        with pytest.raises(AuthError) as exc_info:
            await auth_service.login("ghost@fleet.com", "any_password")
        # Error message must be vague — do not leak email existence
        assert "Invalid email or password" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_login_raises_auth_error_when_password_wrong(
        self, auth_service, mock_repo, mock_hasher
    ):
        # Arrange
        user = _make_user(is_active=True)
        mock_repo.find_by_email.return_value = user
        mock_hasher.verify.return_value = False
        # Act & Assert
        with pytest.raises(AuthError) as exc_info:
            await auth_service.login("employee@fleet.com", "wrong_pass")
        assert "Invalid email or password" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_login_raises_auth_error_when_user_is_inactive(
        self, auth_service, mock_repo, mock_hasher
    ):
        # Arrange — deactivated account cannot log in (SAD §4)
        user = _make_user(is_active=False)
        mock_repo.find_by_email.return_value = user
        mock_hasher.verify.return_value = True
        # Act & Assert
        with pytest.raises(AuthError) as exc_info:
            await auth_service.login("employee@fleet.com", "correct_pass")
        assert "deactivated" in str(exc_info.value).lower() or \
               "Invalid email or password" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_login_normalizes_email_before_lookup(
        self, auth_service, mock_repo, mock_hasher
    ):
        # Arrange
        user = _make_user(email="emp@fleet.com", is_active=True)
        mock_repo.find_by_email.return_value = user
        mock_hasher.verify.return_value = True
        # Act
        await auth_service.login("  EMP@FLEET.COM  ", "pass")
        # Assert — repo.find_by_email must receive the normalized email
        mock_repo.find_by_email.assert_called_once_with("emp@fleet.com")

    @pytest.mark.asyncio
    async def test_login_token_contains_user_id(
        self, auth_service, mock_repo, mock_hasher, jwt_handler
    ):
        # Arrange
        user = _make_user(email="emp@fleet.com", is_active=True)
        user_id = user.id
        mock_repo.find_by_email.return_value = user
        mock_hasher.verify.return_value = True
        # Act
        token = await auth_service.login("emp@fleet.com", "pass")
        # Assert
        import jwt as pyjwt
        payload = pyjwt.decode(token, TEST_SECRET, algorithms=[TEST_ALGORITHM])
        assert payload["sub"] == user_id

    @pytest.mark.asyncio
    async def test_login_token_contains_correct_role(
        self, auth_service, mock_repo, mock_hasher
    ):
        # Arrange
        user = _make_user(role=UserRole.ADMINISTRADOR, is_active=True)
        mock_repo.find_by_email.return_value = user
        mock_hasher.verify.return_value = True
        # Act
        token = await auth_service.login("emp@fleet.com", "pass")
        # Assert
        import jwt as pyjwt
        payload = pyjwt.decode(token, TEST_SECRET, algorithms=[TEST_ALGORITHM])
        assert payload["role"] == "ADMINISTRADOR"
