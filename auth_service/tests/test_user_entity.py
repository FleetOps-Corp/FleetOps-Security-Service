"""
Unit Tests — User Entity (Domain Layer)
=========================================
Coverage target: 100% of User and UserRole public methods.
Pattern: AAA (Arrange → Act → Assert)
SAD Reference: Domain entity for authentication (pág. 5 — <<Domain>> Auth Service)

No infrastructure dependencies — pure domain tests.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.domain.user import User, UserRole

# =============================================================================
# UserRole enum
# =============================================================================

class TestUserRole:

    def test_default_role_is_empleado(self):
        # SAD §3: new users receive EMPLEADO role by default (team agreement)
        assert UserRole.default() == UserRole.EMPLEADO

    def test_all_four_roles_exist(self):
        # SAD §1: exactly 4 roles in the system
        roles = {r.value for r in UserRole}
        assert roles == {
            "EMPLEADO",
            "EMPLEADO_MANTENIMIENTO",
            "EMPLEADO_INCIDENTES",
            "ADMINISTRADOR",
        }

    def test_role_is_string_enum(self):
        assert isinstance(UserRole.EMPLEADO, str)
        assert UserRole.EMPLEADO == "EMPLEADO"


# =============================================================================
# User.create factory
# =============================================================================

class TestUserCreate:

    def test_create_generates_uuid_id(self):
        # Arrange & Act
        user = User.create(email="test@fleetops.com", hashed_password="hashed_pw")
        # Assert
        assert user.id is not None
        assert len(user.id) == 36  # UUID4 canonical form
        assert user.id.count("-") == 4

    def test_create_two_users_have_different_ids(self):
        # Arrange & Act
        u1 = User.create(email="a@fleetops.com", hashed_password="h1")
        u2 = User.create(email="b@fleetops.com", hashed_password="h2")
        # Assert
        assert u1.id != u2.id

    def test_create_normalizes_email_to_lowercase(self):
        # Arrange
        raw_email = "  Admin@FleetOps.COM  "
        # Act
        user = User.create(email=raw_email, hashed_password="hashed")
        # Assert
        assert user.email == "admin@fleetops.com"

    def test_create_sets_default_role_to_empleado(self):
        # SAD §3: default role is EMPLEADO
        user = User.create(email="e@fleetops.com", hashed_password="h")
        assert user.role == UserRole.EMPLEADO

    def test_create_allows_explicit_role_override(self):
        # Arrange — used for admin seeding
        user = User.create(
            email="admin@fleetops.com",
            hashed_password="h",
            role=UserRole.ADMINISTRADOR,
        )
        # Assert
        assert user.role == UserRole.ADMINISTRADOR

    def test_create_sets_is_active_true(self):
        user = User.create(email="x@x.com", hashed_password="h")
        assert user.is_active is True

    def test_create_sets_created_at_and_updated_at(self):
        user = User.create(email="x@x.com", hashed_password="h")
        assert user.created_at is not None
        assert user.updated_at is not None

    def test_create_timestamps_are_timezone_aware(self):
        user = User.create(email="x@x.com", hashed_password="h")
        assert user.created_at.tzinfo is not None
        assert user.updated_at.tzinfo is not None


# =============================================================================
# User.is_password_correct
# =============================================================================

class TestUserIsPasswordCorrect:

    def _make_user(self, is_active: bool = True) -> User:
        return User(
            id="uuid-1",
            email="user@fleetops.com",
            hashed_password="$bcrypt$hashed",
            role=UserRole.EMPLEADO,
            is_active=is_active,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def test_returns_true_when_password_matches_and_user_is_active(self):
        # Arrange
        user = self._make_user(is_active=True)
        verify_fn = MagicMock(return_value=True)
        # Act
        result = user.is_password_correct("correct_password", verify_fn)
        # Assert
        assert result is True
        verify_fn.assert_called_once_with("correct_password", "$bcrypt$hashed")

    def test_returns_false_when_password_does_not_match(self):
        # Arrange
        user = self._make_user(is_active=True)
        verify_fn = MagicMock(return_value=False)
        # Act
        result = user.is_password_correct("wrong_password", verify_fn)
        # Assert
        assert result is False

    def test_returns_false_when_user_is_inactive_regardless_of_password(self):
        # Arrange — deactivated accounts cannot log in (SAD §4: access control)
        user = self._make_user(is_active=False)
        verify_fn = MagicMock(return_value=True)
        # Act
        result = user.is_password_correct("correct_password", verify_fn)
        # Assert
        assert result is False
        # verify_fn should NOT be called for inactive users (short-circuit)
        verify_fn.assert_not_called()

    def test_verify_fn_receives_correct_arguments(self):
        # Arrange
        user = self._make_user(is_active=True)
        verify_fn = MagicMock(return_value=True)
        plain = "my_plain_password"
        # Act
        user.is_password_correct(plain, verify_fn)
        # Assert — verify_fn must receive (plain, hashed) in that order
        verify_fn.assert_called_once_with(plain, user.hashed_password)


# =============================================================================
# User.deactivate
# =============================================================================

class TestUserDeactivate:

    def test_deactivate_sets_is_active_to_false(self):
        # Arrange
        user = User.create(email="a@fleetops.com", hashed_password="h")
        assert user.is_active is True
        # original_updated_at = user.updated_at
        # Act
        user.deactivate()
        # Assert
        assert user.is_active is False

    def test_deactivate_updates_updated_at_timestamp(self):
        # Arrange
        user = User.create(email="a@fleetops.com", hashed_password="h")
        original_updated_at = user.updated_at
        # Act
        user.deactivate()
        # Assert — updated_at must change after deactivation
        assert user.updated_at >= original_updated_at
