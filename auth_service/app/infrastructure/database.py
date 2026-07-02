"""
Auth Service — Database (Infrastructure Layer)
===============================================
SAD Reference: <<Infrastructure>> Auth Service — "SQL · Alembic migrations" (pág. 5)
Pattern: Repository infrastructure — async SQLAlchemy engine setup

Provides the async engine and session factory used by the UserRepository.
The sync engine is used exclusively by Alembic (alembic/env.py).
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# ---------------------------------------------------------------------------
# Async engine — used by the application at runtime
# ---------------------------------------------------------------------------
async_engine = create_async_engine(
    settings.database_url,
    echo=settings.app_env == "development",
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionFactory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """
    Declarative base for all ORM models in the Auth Service.
    Shared with alembic/env.py for schema detection.
    """

    pass


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session.
    Ensures the session is always closed after the request.
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
