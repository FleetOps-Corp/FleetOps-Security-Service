"""
Role Service — ORM Models (Infrastructure Layer)
=================================================
SAD Reference: Infrastructure Layer — "Tablas: roles · user_roles" (pág. 5)
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class RoleModel(Base):
    """Catalog of system roles. Seeded by the Alembic migration."""
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    user_assignments: Mapped[list["UserRoleModel"]] = relationship(
        "UserRoleModel",
        back_populates="role",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"RoleModel(name={self.name!r}, is_active={self.is_active})"


class UserRoleModel(Base):
    """Assignment of a role to a user — administered exclusively by admins (SAD §3)."""
    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    role_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    assigned_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    role: Mapped[RoleModel] = relationship("RoleModel", back_populates="user_assignments")

    def __repr__(self) -> str:
        return f"UserRoleModel(user_id={self.user_id!r}, role_id={self.role_id!r})"
