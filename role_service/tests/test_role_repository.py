"""
Unit Tests — RoleRepository (Infrastructure Layer)
====================================================
Coverage target: 100% of RoleRepository public methods.
Pattern: AAA (Arrange → Act → Assert)
SAD Reference: Cache-aside Redis (pág. 10), SQL queries (pág. 5)
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.role import Role, UserRoleAssignment
from app.infrastructure.models import RoleModel, UserRoleModel
from app.infrastructure.role_repository import RoleRepository

# =============================================================================
# Helpers
# =============================================================================

def _make_role_model(name: str = "EMPLEADO", is_active: bool = True) -> RoleModel:
    model = RoleModel()
    model.id = "role-id-1"
    model.name = name
    model.description = "Test role"
    model.is_active = is_active
    model.created_at = datetime.now(timezone.utc)
    return model


def _make_user_role_model(user_id: str, role_name: str = "EMPLEADO") -> UserRoleModel:
    role_model = _make_role_model(name=role_name)
    model = UserRoleModel()
    model.id = "assignment-id-1"
    model.user_id = user_id
    model.role_id = "role-id-1"
    model.assigned_at = datetime.now(timezone.utc)
    model.assigned_by = None
    model.role = role_model
    return model


def _make_repo(session=None, redis=None) -> RoleRepository:
    if session is None:
        session = AsyncMock()
    if redis is None:
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        redis.delete = AsyncMock()
    return RoleRepository(session=session, redis_client=redis)


# =============================================================================
# find_role_by_name
# =============================================================================

class TestFindRoleByName:

    @pytest.mark.asyncio
    async def test_returns_role_when_found(self):
        model = _make_role_model(name="ADMINISTRADOR")
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = model
        session.execute = AsyncMock(return_value=result_mock)
        repo = _make_repo(session=session)
        result = await repo.find_role_by_name("ADMINISTRADOR")
        assert result is not None
        assert result.name == "ADMINISTRADOR"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)
        repo = _make_repo(session=session)
        result = await repo.find_role_by_name("NONEXISTENT")
        assert result is None


# =============================================================================
# find_roles_by_user_id — cache-aside logic
# =============================================================================

class TestFindRolesByUserId:

    @pytest.mark.asyncio
    async def test_returns_roles_from_redis_cache_on_hit(self):
        # Arrange — Redis returns cached JSON
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=json.dumps(["EMPLEADO", "ADMINISTRADOR"]))
        redis.setex = AsyncMock()
        repo = _make_repo(redis=redis)
        # Act
        result = await repo.find_roles_by_user_id("u-1")
        # Assert
        role_names = {a.role_name for a in result}
        assert role_names == {"EMPLEADO", "ADMINISTRADOR"}
        # DB must NOT be queried on cache hit
        repo._session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_queries_db_on_cache_miss_and_populates_cache(self):
        # Arrange
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()

        user_role_model = _make_user_role_model("u-1", "EMPLEADO_MANTENIMIENTO")
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [user_role_model]
        session.execute = AsyncMock(return_value=result_mock)

        repo = _make_repo(session=session, redis=redis)
        result = await repo.find_roles_by_user_id("u-1")

        assert len(result) == 1
        assert result[0].role_name == "EMPLEADO_MANTENIMIENTO"
        redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_user_has_no_roles(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()

        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=result_mock)

        repo = _make_repo(session=session, redis=redis)
        result = await repo.find_roles_by_user_id("u-no-roles")
        assert result == []

    @pytest.mark.asyncio
    async def test_does_not_fail_when_redis_is_unavailable(self):
        # SAD: Fiabilidad — Redis failure must not break the service
        redis = AsyncMock()
        redis.get = AsyncMock(side_effect=Exception("Connection refused"))
        redis.setex = AsyncMock(side_effect=Exception("Connection refused"))

        user_role_model = _make_user_role_model("u-1", "EMPLEADO")
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [user_role_model]
        session.execute = AsyncMock(return_value=result_mock)

        repo = _make_repo(session=session, redis=redis)
        result = await repo.find_roles_by_user_id("u-1")
        assert len(result) == 1


# =============================================================================
# assign_role_to_user
# =============================================================================

class TestAssignRoleToUser:

    @pytest.mark.asyncio
    async def test_adds_model_and_flushes(self):
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        redis = AsyncMock()
        redis.delete = AsyncMock()
        repo = _make_repo(session=session, redis=redis)

        assignment = UserRoleAssignment(
            id="a-id",
            user_id="u-1",
            role_id="r-1",
            role_name="EMPLEADO",
            assigned_at=datetime.now(timezone.utc),
            assigned_by=None,
        )
        
        await repo.assign_role_to_user(assignment)
        
        session.add.assert_called_once()
        session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidates_user_role_cache_on_assignment(self):
        # [Archetype Convention Addition] — cache invalidation on write
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        redis = AsyncMock()
        redis.delete = AsyncMock()
        repo = _make_repo(session=session, redis=redis)

        assignment = UserRoleAssignment(
            id="a-id",
            user_id="u-invalidate",
            role_id="r-1",
            role_name="EMPLEADO",
            assigned_at=datetime.now(timezone.utc),
            assigned_by=None,
        )
        await repo.assign_role_to_user(assignment)
        redis.delete.assert_called_once()


# =============================================================================
# save_role
# =============================================================================

class TestSaveRole:

    @pytest.mark.asyncio
    async def test_save_role_adds_to_session_and_flushes(self):
        # Arrange
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        repo = _make_repo(session=session)
        role = Role.create("EMPLEADO_MANTENIMIENTO", "Maintenance")
        # Act
        result = await repo.save_role(role)
        # Assert
        session.add.assert_called_once()
        session.flush.assert_called_once()
        assert result is role

    @pytest.mark.asyncio
    async def test_save_role_returns_the_same_domain_object(self):
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        repo = _make_repo(session=session)
        role = Role.create("ADMINISTRADOR")
        result = await repo.save_role(role)
        assert result.name == "ADMINISTRADOR"


# =============================================================================
# remove_role_from_user
# =============================================================================

class TestRemoveRoleFromUser:

    @pytest.mark.asyncio
    async def test_returns_false_when_role_does_not_exist(self):
        # Arrange
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)
        repo = _make_repo(session=session)
        # Act
        result = await repo.remove_role_from_user("u-1", "NONEXISTENT")
        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_row_deleted(self):
        # Arrange — first execute finds the role model, second execute deletes
        session = AsyncMock()
        role_model = _make_role_model(name="EMPLEADO")
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = role_model
        delete_result = MagicMock()
        delete_result.rowcount = 1
        session.execute = AsyncMock(side_effect=[find_result, delete_result])

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        redis.delete = AsyncMock()

        repo = _make_repo(session=session, redis=redis)
        result = await repo.remove_role_from_user("u-1", "EMPLEADO")
        assert result is True

    @pytest.mark.asyncio
    async def test_invalidates_cache_on_removal(self):
        # Arrange
        session = AsyncMock()
        role_model = _make_role_model(name="EMPLEADO")
        find_result = MagicMock()
        find_result.scalar_one_or_none.return_value = role_model
        delete_result = MagicMock()
        delete_result.rowcount = 1
        session.execute = AsyncMock(side_effect=[find_result, delete_result])

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        redis.delete = AsyncMock()

        repo = _make_repo(session=session, redis=redis)
        await repo.remove_role_from_user("u-invalidate", "EMPLEADO")
        redis.delete.assert_called_once()


# =============================================================================
# role_exists_by_name
# =============================================================================

class TestRoleExistsByName:

    @pytest.mark.asyncio
    async def test_returns_true_when_role_exists(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = "some-id"
        session.execute = AsyncMock(return_value=result_mock)
        repo = _make_repo(session=session)
        result = await repo.role_exists_by_name("EMPLEADO")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_role_does_not_exist(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)
        repo = _make_repo(session=session)
        result = await repo.role_exists_by_name("GHOST_ROLE")
        assert result is False
