"""
Unit Tests — RoleDomainService (Domain Layer)
===============================================
Coverage target: 100% of RoleDomainService public methods.
Pattern: AAA (Arrange → Act → Assert)
SAD Reference: RBAC logic (§1, §4, pág. 10)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.domain.role import Role, UserRoleAssignment
from app.domain.role_service import RoleAssignmentError, RoleDomainService, RoleNotFoundError

# =============================================================================
# Fixtures
# =============================================================================

def _make_role(name: str = "EMPLEADO", is_active: bool = True) -> Role:
    return Role(
        id="role-uuid-1",
        name=name,
        description="Test role",
        is_active=is_active,
        created_at=datetime.now(timezone.utc),
    )


def _make_assignment(user_id: str = "u-1", role_name: str = "EMPLEADO") -> UserRoleAssignment:
    return UserRoleAssignment(
        id="assign-uuid-1",
        user_id=user_id,
        role_id="role-uuid-1",
        role_name=role_name,
        assigned_at=datetime.now(timezone.utc),
        assigned_by=None,
    )


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_role_by_name = AsyncMock(return_value=None)
    repo.find_roles_by_user_id = AsyncMock(return_value=[])
    repo.save_role = AsyncMock(side_effect=lambda r: r)
    repo.assign_role_to_user = AsyncMock(side_effect=lambda a: a)
    repo.remove_role_from_user = AsyncMock(return_value=True)
    repo.role_exists_by_name = AsyncMock(return_value=False)
    return repo


@pytest.fixture
def svc(mock_repo) -> RoleDomainService:
    return RoleDomainService(role_repository=mock_repo)


# =============================================================================
# get_user_roles
# =============================================================================

class TestGetUserRoles:

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_user_has_no_roles(self, svc, mock_repo):
        mock_repo.find_roles_by_user_id.return_value = []
        result = await svc.get_user_roles("u-1")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_role_names_for_user(self, svc, mock_repo):
        mock_repo.find_roles_by_user_id.return_value = [
            _make_assignment(role_name="EMPLEADO"),
            _make_assignment(role_name="ADMINISTRADOR"),
        ]
        result = await svc.get_user_roles("u-1")
        assert set(result) == {"EMPLEADO", "ADMINISTRADOR"}

    @pytest.mark.asyncio
    async def test_calls_repo_with_correct_user_id(self, svc, mock_repo):
        user_id = "specific-user-id"
        await svc.get_user_roles(user_id)
        mock_repo.find_roles_by_user_id.assert_called_once_with(user_id)


# =============================================================================
# validate_user_has_any_role
# =============================================================================

class TestValidateUserHasAnyRole:

    @pytest.mark.asyncio
    async def test_returns_true_when_user_has_required_role(self, svc, mock_repo):
        mock_repo.find_roles_by_user_id.return_value = [
            _make_assignment(role_name="ADMINISTRADOR")
        ]
        result = await svc.validate_user_has_any_role("u-1", ["ADMINISTRADOR"])
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_user_lacks_required_role(self, svc, mock_repo):
        mock_repo.find_roles_by_user_id.return_value = [
            _make_assignment(role_name="EMPLEADO")
        ]
        result = await svc.validate_user_has_any_role("u-1", ["ADMINISTRADOR"])
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_required_roles_is_empty(self, svc, mock_repo):
        # Empty required_roles means public access
        result = await svc.validate_user_has_any_role("u-1", [])
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_when_user_has_one_of_multiple_required_roles(
        self, svc, mock_repo
    ):
        mock_repo.find_roles_by_user_id.return_value = [
            _make_assignment(role_name="EMPLEADO_MANTENIMIENTO")
        ]
        result = await svc.validate_user_has_any_role(
            "u-1", ["ADMINISTRADOR", "EMPLEADO_MANTENIMIENTO"]
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_comparison_is_case_insensitive(self, svc, mock_repo):
        mock_repo.find_roles_by_user_id.return_value = [
            _make_assignment(role_name="ADMINISTRADOR")
        ]
        result = await svc.validate_user_has_any_role("u-1", ["administrador"])
        assert result is True


# =============================================================================
# assign_role
# =============================================================================

class TestAssignRole:

    @pytest.mark.asyncio
    async def test_assign_role_returns_assignment(self, svc, mock_repo):
        role = _make_role(name="EMPLEADO_MANTENIMIENTO", is_active=True)
        mock_repo.find_role_by_name.return_value = role
        mock_repo.assign_role_to_user.return_value = _make_assignment(
            role_name="EMPLEADO_MANTENIMIENTO"
        )
        result = await svc.assign_role("u-1", "EMPLEADO_MANTENIMIENTO", "admin-1")
        assert isinstance(result, UserRoleAssignment)

    @pytest.mark.asyncio
    async def test_assign_raises_role_not_found_when_role_missing(
        self, svc, mock_repo
    ):
        mock_repo.find_role_by_name.return_value = None
        with pytest.raises(RoleNotFoundError) as exc_info:
            await svc.assign_role("u-1", "NONEXISTENT_ROLE")
        assert "NONEXISTENT_ROLE" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_assign_raises_error_when_role_is_inactive(self, svc, mock_repo):
        inactive_role = _make_role(name="EMPLEADO", is_active=False)
        mock_repo.find_role_by_name.return_value = inactive_role
        with pytest.raises(RoleAssignmentError) as exc_info:
            await svc.assign_role("u-1", "EMPLEADO")
        assert "disabled" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_assign_calls_repo_with_correct_user_and_role(
        self, svc, mock_repo
    ):
        role = _make_role(name="ADMINISTRADOR", is_active=True)
        mock_repo.find_role_by_name.return_value = role
        assignment = _make_assignment(user_id="u-99", role_name="ADMINISTRADOR")
        mock_repo.assign_role_to_user.return_value = assignment
        await svc.assign_role("u-99", "ADMINISTRADOR", "super-admin")
        mock_repo.assign_role_to_user.assert_called_once()


# =============================================================================
# remove_role
# =============================================================================

class TestRemoveRole:

    @pytest.mark.asyncio
    async def test_remove_role_returns_true_on_success(self, svc, mock_repo):
        mock_repo.remove_role_from_user.return_value = True
        result = await svc.remove_role("u-1", "EMPLEADO")
        assert result is True

    @pytest.mark.asyncio
    async def test_remove_role_raises_not_found_when_not_assigned(
        self, svc, mock_repo
    ):
        mock_repo.remove_role_from_user.return_value = False
        with pytest.raises(RoleNotFoundError) as exc_info:
            await svc.remove_role("u-1", "EMPLEADO")
        assert "u-1" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_remove_role_passes_uppercase_role_name(self, svc, mock_repo):
        mock_repo.remove_role_from_user.return_value = True
        await svc.remove_role("u-1", "empleado")
        mock_repo.remove_role_from_user.assert_called_once_with("u-1", "EMPLEADO")
