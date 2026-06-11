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

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


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
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="EMPLEADO",
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

    def __repr__(self) -> str:
        return f"UserModel(id={self.id!r}, email={self.email!r}, role={self.role!r})"
