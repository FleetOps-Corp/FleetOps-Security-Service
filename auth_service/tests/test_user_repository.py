"""
Unit Tests — UserRepository (Infrastructure Layer)
====================================================
Coverage target: 100% of UserRepository public methods.
Pattern: AAA (Arrange → Act → Assert)
SAD Reference: "Repo usuarios · bcrypt · SQL" (pág. 5), cache-aside Redis (pág. 9)

SQLAlchemy session and Redis client are fully mocked.
No real database or Redis connection required.
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.user import User, UserRole
from app.infrastructure.models import UserModel
from app.infrastructure.user_repository import UserRepository

# =============================================================================
# Helpers
# =============================================================================

def _make_user_model(
    email: str = "emp@fleet.com",
    role: str = "EMPLEADO",
    is_active: bool = True,
) -> UserModel:
    model = UserModel()
    model.id = "model-uuid-1"
    model.email = email
    model.hashed_password = "$bcrypt$hash"
    model.role = role
    model.is_active = is_active
    model.created_at = datetime.now(timezone.utc)
    model.updated_at = datetime.now(timezone.utc)
    return model


def _make_domain_user(**kwargs) -> User:
    defaults = dict(
        id="domain-uuid-1",
        email="emp@fleet.com",
        hashed_password="$bcrypt$hash",
        role=UserRole.EMPLEADO,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    return User(**defaults)


def _make_repo(
    session: AsyncMock | None = None,
    redis: AsyncMock | None = None,
) -> UserRepository:
    if session is None:
        session = AsyncMock()
    if redis is None:
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock(return_value=True)
    return UserRepository(session=session, redis_client=redis)


# =============================================================================
# _to_domain (static — tested indirectly via find_by_email)
# =============================================================================

class TestToDomain:

    def test_to_domain_maps_all_fields_correctly(self):
        # Arrange
        model = _make_user_model(email="x@y.com", role="ADMINISTRADOR", is_active=True)
        # Act
        user = UserRepository._to_domain(model)
        # Assert
        assert user.id == model.id
        assert user.email == model.email
        assert user.hashed_password == model.hashed_password
        assert user.role == UserRole.ADMINISTRADOR
        assert user.is_active is True

    def test_to_domain_converts_role_string_to_enum(self):
        model = _make_user_model(role="EMPLEADO_MANTENIMIENTO")
        user = UserRepository._to_domain(model)
        assert user.role == UserRole.EMPLEADO_MANTENIMIENTO


# =============================================================================
# find_by_email
# =============================================================================

class TestFindByEmail:

    @pytest.mark.asyncio
    async def test_returns_user_from_redis_cache_on_hit(self):
        # Arrange — Redis returns cached JSON
        user = _make_domain_user()
        cached_data = {
            "id": user.id,
            "email": user.email,
            "hashed_password": user.hashed_password,
            "role": user.role.value,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat(),
        }
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=json.dumps(cached_data))
        redis.setex = AsyncMock()
        repo = _make_repo(redis=redis)
        # Act
        result = await repo.find_by_email("emp@fleet.com")
        # Assert
        assert result is not None
        assert result.id == user.id
        # DB must NOT be queried on cache hit
        repo._session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_queries_db_on_redis_cache_miss(self):
        # Arrange — Redis returns None (cache miss)
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()

        model = _make_user_model()
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        session.execute = AsyncMock(return_value=mock_result)

        repo = _make_repo(session=session, redis=redis)
        # Act
        result = await repo.find_by_email("emp@fleet.com")
        # Assert
        assert result is not None
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_not_in_cache_or_db(self):
        # Arrange — both Redis and DB return nothing
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        repo = _make_repo(session=session, redis=redis)
        # Act
        result = await repo.find_by_email("ghost@fleet.com")
        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_populates_cache_after_db_hit(self):
        # Arrange
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()

        model = _make_user_model()
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        session.execute = AsyncMock(return_value=mock_result)

        repo = _make_repo(session=session, redis=redis)
        # Act
        await repo.find_by_email("emp@fleet.com")
        # Assert — Redis.setex must be called after DB hit (cache-aside write)
        redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_does_not_fail_when_redis_is_unavailable(self):
        # SAD §3: Fiabilidad — Tolerancia de fallos — Redis failure is non-fatal
        redis = AsyncMock()
        redis.get = AsyncMock(side_effect=Exception("Redis connection refused"))
        redis.setex = AsyncMock(side_effect=Exception("Redis connection refused"))

        model = _make_user_model()
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        session.execute = AsyncMock(return_value=mock_result)

        repo = _make_repo(session=session, redis=redis)
        # Act — should NOT raise even when Redis is down
        result = await repo.find_by_email("emp@fleet.com")
        # Assert — falls back to DB result
        assert result is not None


# =============================================================================
# save
# =============================================================================

class TestSave:

    @pytest.mark.asyncio
    async def test_save_adds_model_to_session(self):
        # Arrange
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        
        repo = _make_repo(session=session)
        user = _make_domain_user()
        # Act
        await repo.save(user)

        # Assert
        session.add.assert_called_once()
        session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_returns_the_same_user_entity(self):
        # Arrange
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        repo = _make_repo(session=session)
        user = _make_domain_user()
        # Act
        result = await repo.save(user)
        # Assert
        assert result is user


# =============================================================================
# exists_by_email
# =============================================================================

class TestExistsByEmail:

    @pytest.mark.asyncio
    async def test_returns_true_when_user_exists(self):
        # Arrange
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "some-uuid"
        session.execute = AsyncMock(return_value=mock_result)
        repo = _make_repo(session=session)
        # Act
        result = await repo.exists_by_email("existing@fleet.com")
        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_user_does_not_exist(self):
        # Arrange
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)
        repo = _make_repo(session=session)
        # Act
        result = await repo.exists_by_email("ghost@fleet.com")
        # Assert
        assert result is False
