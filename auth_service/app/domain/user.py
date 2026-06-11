"""
Auth Service — User Entity (Domain Layer)
==========================================
SAD Reference: <<Domain>> Auth Service — "Autenticación, Lógica de login y
               registro, Servicio de negocio · JWT" (pág. 5 diagram)
Pattern: Domain Entity (DDD)

The User entity encapsulates identity and password-verification logic.
It has NO dependency on infrastructure (no SQLAlchemy, no Redis here).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable


class UserRole(str, Enum):
    """
    Canonical role enumeration.
    SAD §1: Roles del sistema FleetOps.
    Confirmed: new users default to EMPLEADO (team agreement §1 confirmation).
    """
    EMPLEADO = "EMPLEADO"
    EMPLEADO_MANTENIMIENTO = "EMPLEADO_MANTENIMIENTO"
    EMPLEADO_INCIDENTES = "EMPLEADO_INCIDENTES"
    ADMINISTRADOR = "ADMINISTRADOR"

    @classmethod
    def default(cls) -> "UserRole":
        """SAD §3: new users receive basic EMPLEADO role by default."""
        return cls.EMPLEADO


@dataclass
class User:
    """
    Domain entity representing a registered FleetOps user.

    This is a plain Python dataclass — no ORM decorators, no framework.
    Infrastructure concerns (persistence, hashing) are handled in the
    repository and domain service layers respectively.
    """
    id: str
    email: str
    hashed_password: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        email: str,
        hashed_password: str,
        role: UserRole | None = None,
    ) -> "User":
        """
        Factory method: creates a new User with a generated UUID and defaults.

        Args:
            email:           User's email address (must be validated before call).
            hashed_password: Bcrypt hash — NEVER a plain-text password.
            role:            Role to assign. Defaults to UserRole.EMPLEADO (SAD §3).

        Returns:
            A new User domain entity (not yet persisted).
        """
        now = datetime.now(timezone.utc)
        return cls(
            id=str(uuid.uuid4()),
            email=email.lower().strip(),
            hashed_password=hashed_password,
            role=role or UserRole.default(),
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def is_password_correct(self, plain_password: str, verify_fn: Callable[[str, str], bool]) -> bool:
        """
        Verifies a plain-text password against the stored hash.

        Args:
            plain_password: The password provided by the user at login.
            verify_fn:      A callable(plain, hashed) -> bool that performs
                            the actual bcrypt verification. Injected to keep
                            the domain layer free of passlib imports.

        Returns:
            True if the password matches, False otherwise.
        """
        if not self.is_active:
            return False
        return verify_fn(plain_password, self.hashed_password)

    def deactivate(self) -> None:
        """Marks the user as inactive (soft delete)."""
        self.is_active = False
        self.updated_at = datetime.now(timezone.utc)
