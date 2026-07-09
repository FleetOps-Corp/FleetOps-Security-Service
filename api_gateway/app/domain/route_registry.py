"""
API Gateway — Route Registry (Domain Layer)
============================================
SAD Reference: "Api gateway contendrá el diccionario de roles junto con
               todas las rutas disponibles del sistema" (pág. 4)
Pattern: Service Locator / Route Dictionary

This module is the authoritative source of truth for:
  - Which downstream microservice handles each route prefix
  - Which roles are allowed to access each route

Roles (SAD §1 — RBAC):
  - EMPLEADO:               own assignments (route + vehicle)
  - EMPLEADO_MANTENIMIENTO: vehicle info for maintenance
  - EMPLEADO_INCIDENTES:    vehicle + driver info for incident management
  - ADMINISTRADOR:          vehicles, incidents, maintenance — strategic reports

Architecture note: The route registry lives in the Domain layer because
it encodes business authorization rules, not infrastructure concerns.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.config import settings


class Role(str, Enum):
    """
    Enumeration of all system roles.
    SAD §1: Roles pensados para el sistema FleetOps.
    """

    EMPLEADO = "EMPLEADO"
    EMPLEADO_MANTENIMIENTO = "EMPLEADO_MANTENIMIENTO"
    EMPLEADO_INCIDENTES = "EMPLEADO_INCIDENTES"
    EMPLEADO_VEHICULOS = "EMPLEADO_VEHICULOS"
    EMPLEADO_ASIGNACIONES = "EMPLEADO_ASIGNACIONES"
    EMPLEADO_REPORTES = "EMPLEADO_REPORTES"
    ADMINISTRADOR = "ADMINISTRADOR"


@dataclass(frozen=True)
class RouteEntry:
    """
    Represents a single routing rule in the Gateway dictionary.

    Attributes:
        prefix:          URL prefix to match (e.g. "/vehiculos")
        upstream_url_key: Key in settings pointing to the target service URL
        allowed_roles:   Set of roles permitted to access this route prefix.
                         Empty set means the route is publicly accessible
                         (e.g. /auth/login, /auth/register).
        description:     Human-readable description for documentation.
    """

    prefix: str
    upstream_url_key: str

    # CORRECCIÓN: Se añade [Role] para que MyPy sepa qué contiene el set
    allowed_roles: frozenset[Role] = field(default_factory=frozenset)
    description: str = ""

    def is_public(self) -> bool:
        """Returns True if this route requires no authentication."""
        return len(self.allowed_roles) == 0

    def allows_role(self, role: str) -> bool:
        """
        Returns True if the given role string is permitted for this route.
        Comparison is case-insensitive.
        """
        return role.upper() in {r.value for r in self.allowed_roles}


class RouteRegistry:
    """
    Domain service that holds the complete route dictionary.
    SAD §3: "Api gateway contendrá el diccionario de roles junto con
            todas las rutas disponibles del sistema"

    Pattern: Registry (POSA Vol. 1)
    """

    def __init__(self) -> None:
        self._routes: list[RouteEntry] = self._build_routes()

    def _build_routes(self) -> list[RouteEntry]:
        """
        Constructs the authoritative route table.
        Order matters: first match wins.
        Public routes (auth) must come before protected catch-alls.
        """
        return [
            # ------------------------------------------------------------------
            # Public routes — no authentication required (SAD §3: login/register
            # are the only publicly accessible endpoints)
            # ------------------------------------------------------------------
            RouteEntry(
                prefix="/auth",
                upstream_url_key="auth_service_url",
                allowed_roles=frozenset(),
                description="Authentication endpoints: /auth/login, /auth/register, /auth/refresh",
            ),
            # ------------------------------------------------------------------
            # Roles — ADMINISTRADOR only
            # SAD §3: "la administración del sistema" assigns and removes roles.
            # ------------------------------------------------------------------
            RouteEntry(
                prefix="/roles",
                upstream_url_key="role_service_url",
                allowed_roles=frozenset(
                    {
                        Role.ADMINISTRADOR,
                    }
                ),
                description="Role management microservice: /roles/assign, /roles/remove, /roles/user",
            ),
            # ------------------------------------------------------------------
            # Vehículos — EMPLEADO_MANTENIMIENTO, EMPLEADO_INCIDENTES, ADMINISTRADOR
            # SAD §1: Empleado de mantenimiento accede a info relevante del vehículo.
            #         Empleado de incidentes accede a info del vehículo y conductor.
            #         Administrador accede para generar informes estratégicos.
            # ------------------------------------------------------------------
            RouteEntry(
                prefix=settings.vehicles_service_prefix,
                upstream_url_key="vehicles_service_url",
                allowed_roles=frozenset(
                    {
                        Role.EMPLEADO_MANTENIMIENTO,
                        Role.EMPLEADO_INCIDENTES,
                        Role.EMPLEADO_ASIGNACIONES,
                        Role.EMPLEADO_REPORTES,
                        Role.ADMINISTRADOR,
                    }
                ),
                description="Vehicle management microservice",
            ),
            # ------------------------------------------------------------------
            # Asignaciones — EMPLEADO, ADMINISTRADOR
            # SAD §1: Empleado accede a sus asignaciones (ruta + vehículo).
            # ------------------------------------------------------------------
            RouteEntry(
                prefix=settings.assignments_service_prefix,
                upstream_url_key="assignments_service_url",
                allowed_roles=frozenset(
                    {
                        Role.EMPLEADO_VEHICULOS,
                        Role.EMPLEADO_REPORTES,
                        Role.ADMINISTRADOR,
                    }
                ),
                description="Assignment management microservice",
            ),
            # ------------------------------------------------------------------
            # Incidentes — EMPLEADO_INCIDENTES, ADMINISTRADOR
            # SAD §1: Empleado de incidentes gestiona incidentes mecánicos o humanos.
            # ------------------------------------------------------------------
            RouteEntry(
                prefix="api/incidents",
                upstream_url_key="incidents_service_url",
                allowed_roles=frozenset(
                    {
                        Role.EMPLEADO_VEHICULOS,
                        Role.EMPLEADO_MANTENIMIENTO,
                        Role.EMPLEADO_ASIGNACIONES,
                        Role.EMPLEADO_REPORTES,
                        Role.ADMINISTRADOR,
                    }
                ),
                description="Incident management microservice",
            ),
            # ------------------------------------------------------------------
            # Mantenimiento — EMPLEADO_MANTENIMIENTO, ADMINISTRADOR
            # SAD §1: Empleado de mantenimiento accede a info de mantenimiento.
            # ------------------------------------------------------------------
            RouteEntry(
                prefix=settings.maintenance_service_prefix,
                upstream_url_key="maintenance_service_url",
                allowed_roles=frozenset(
                    {
                        Role.EMPLEADO_VEHICULOS,
                        Role.EMPLEADO_REPORTES,
                        Role.ADMINISTRADOR,
                    }
                ),
                description="Maintenance management microservice",
            ),
            # ------------------------------------------------------------------
            # Reportes — ADMINISTRADOR only
            # SAD §1: Administrador genera informes estratégicos.
            # ------------------------------------------------------------------
            RouteEntry(
                prefix=settings.reports_service_prefix,
                upstream_url_key="reports_service_url",
                allowed_roles=frozenset(
                    {
                        Role.ADMINISTRADOR,
                    }
                ),
                description="Reports microservice — strategic reports",
            ),
        ]

    def find_route(self, path: str) -> Optional[RouteEntry]:
        """
        Finds the first RouteEntry whose prefix matches the beginning of path.

        Args:
            path: The request path (e.g. "/vehiculos/123")

        Returns:
            The matching RouteEntry, or None if no route is registered.
        """
        for route in self._routes:
            if path.startswith(route.prefix):
                return route
        return None

    def get_all_routes(self) -> list[RouteEntry]:
        """Returns a copy of all registered routes (for documentation/testing)."""
        return list(self._routes)
