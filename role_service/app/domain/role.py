"""
Role Service — Role and UserRole Entities (Domain Layer)
=========================================================
SAD Reference: <<Domain>> Role Service — "Gestión de rol, Crear · Consultar ·
               Modificar · Inhabilitar roles · RBAC logic" (pág. 5)
Pattern: Domain Entity (DDD)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class RoleName(str, Enum):
    """Canonical role names (SAD §1)."""

    EMPLEADO = "EMPLEADO"
    EMPLEADO_MANTENIMIENTO = "EMPLEADO_MANTENIMIENTO"
    EMPLEADO_INCIDENTES = "EMPLEADO_INCIDENTES"
    EMPLEADO_VEHICULOS = "EMPLEADO_VEHICULOS"
    EMPLEADO_ASIGNACIONES = "EMPLEADO_ASIGNACIONES"
    EMPLEADO_REPORTES = "EMPLEADO_REPORTES"
    ADMINISTRADOR = "ADMINISTRADOR"


@dataclass
class Role:
    """
    Domain entity representing a system role.
    SAD §1: roles that define access boundaries in FleetOps.
    """

    id: str
    name: str
    description: str
    is_active: bool
    created_at: datetime

    @classmethod
    def create(cls, name: str, description: str = "") -> "Role":
        return cls(
            id=str(uuid.uuid4()),
            name=name.upper().strip(),
            description=description,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )

    def deactivate(self) -> None:
        """SAD §5: Inhabilitar roles."""
        self.is_active = False

    def activate(self) -> None:
        self.is_active = True


@dataclass
class UserRoleAssignment:
    """
    Domain entity representing the assignment of a role to a user.
    SAD: user_roles table — admins assign roles, users cannot self-assign (§3).
    """

    id: str
    user_id: str
    role_id: str
    role_name: str
    assigned_at: datetime
    assigned_by: Optional[str]

    @classmethod
    def create(
        cls,
        user_id: str,
        role_id: str,
        role_name: str,
        assigned_by: Optional[str] = None,
    ) -> "UserRoleAssignment":
        """
        Factory method for creating a new role assignment.
        SAD §3: "la administración del sistema" assigns roles.
        """
        return cls(
            id=str(uuid.uuid4()),
            user_id=user_id,
            role_id=role_id,
            role_name=role_name,
            assigned_at=datetime.now(timezone.utc),
            assigned_by=assigned_by,
        )
