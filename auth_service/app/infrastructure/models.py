"""
Auth Service — ORM Models (Infrastructure Layer)
=================================================
SAD Reference: <<Infrastructure>> Auth Service — "Repo usuarios" (pág. 5)
               Infrastructure Layer — "Tablas: users" (pág. 5 diagram)
Pattern: Active Record / Data Mapper (SQLAlchemy declarative)

These models are infrastructure artifacts — they live in the infrastructure
layer and are NEVER imported by the domain layer. Domain entities (User)
are reconstructed from these models by the repository.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class RoleModel(Base):
    """Reflejo simplificado del catálogo de roles para uso exclusivo de autenticación."""

    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)


class UserModel(Base):
    """
    SQLAlchemy ORM model for the 'users' table.
    SAD Reference: Infrastructure Layer — tablas: users (pág. 5)
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # SAD §1: roles del sistema — stored as string for simplicity
    role_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        default="10131318-c79e-4691-91c3-30cd60056ab7",
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    role: Mapped["RoleModel"] = relationship("RoleModel")

    def __repr__(self) -> str:
        return f"UserModel(id={self.id!r}, email={self.email!r}, role={self.role!r})"
