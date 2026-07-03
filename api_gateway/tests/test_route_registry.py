"""
Unit Tests — RouteRegistry (Domain Layer)
==========================================
Coverage target: 100% of RouteRegistry and RouteEntry public methods.
Pattern: AAA (Arrange → Act → Assert)
SAD Reference: Route dictionary (§3), RBAC roles (§1)

No infrastructure dependencies — pure domain tests.
"""

import pytest

from app.config import settings
from app.domain.route_registry import Role, RouteEntry, RouteRegistry

# =============================================================================
# RouteEntry tests
# =============================================================================


class TestRouteEntry:
    """Tests for the RouteEntry value object."""

    def test_is_public_returns_true_when_no_roles(self):
        # Arrange
        entry = RouteEntry(
            prefix="/auth",
            upstream_url_key="auth_service_url",
            allowed_roles=frozenset(),
        )
        # Act
        result = entry.is_public()
        # Assert
        assert result is True

    def test_is_public_returns_false_when_roles_present(self):
        # Arrange
        entry = RouteEntry(
            prefix=settings.vehicles_service_prefix,
            upstream_url_key="vehicles_service_url",
            allowed_roles=frozenset({Role.ADMINISTRADOR}),
        )
        # Act
        result = entry.is_public()
        # Assert
        assert result is False

    def test_allows_role_returns_true_for_permitted_role(self):
        # Arrange
        entry = RouteEntry(
            prefix=settings.vehicles_service_prefix,
            upstream_url_key="vehicles_service_url",
            allowed_roles=frozenset({Role.ADMINISTRADOR, Role.EMPLEADO_MANTENIMIENTO}),
        )
        # Act & Assert
        assert entry.allows_role("ADMINISTRADOR") is True
        assert entry.allows_role("EMPLEADO_MANTENIMIENTO") is True

    def test_allows_role_returns_false_for_unpermitted_role(self):
        # Arrange
        entry = RouteEntry(
            prefix=settings.vehicles_service_prefix,
            upstream_url_key="vehicles_service_url",
            allowed_roles=frozenset({Role.ADMINISTRADOR}),
        )
        # Act
        result = entry.allows_role("EMPLEADO")
        # Assert
        assert result is False

    def test_allows_role_is_case_insensitive(self):
        # Arrange
        entry = RouteEntry(
            prefix=settings.reports_service_prefix,
            upstream_url_key="reports_service_url",
            allowed_roles=frozenset({Role.ADMINISTRADOR}),
        )
        # Act & Assert
        assert entry.allows_role("administrador") is True
        assert entry.allows_role("ADMINISTRADOR") is True
        assert entry.allows_role("Administrador") is True

    def test_allows_role_returns_false_for_unknown_role(self):
        # Arrange
        entry = RouteEntry(
            prefix=settings.reports_service_prefix,
            upstream_url_key="reports_service_url",
            allowed_roles=frozenset({Role.ADMINISTRADOR}),
        )
        # Act
        result = entry.allows_role("SUPER_ADMIN")
        # Assert
        assert result is False

    def test_route_entry_is_immutable(self):
        # Arrange
        entry = RouteEntry(
            prefix=settings.vehicles_service_prefix,
            upstream_url_key="vehicles_service_url",
            allowed_roles=frozenset({Role.ADMINISTRADOR}),
        )
        # Act & Assert — frozen=True means assignment raises FrozenInstanceError
        with pytest.raises((AttributeError, TypeError)):
            entry.prefix = "/other"  # type: ignore[misc]


# =============================================================================
# RouteRegistry tests
# =============================================================================


class TestRouteRegistry:
    """Tests for the RouteRegistry domain service."""

    def setup_method(self):
        """Instantiate a fresh registry before each test."""
        self.registry = RouteRegistry()

    # -------------------------------------------------------------------------
    # find_route — SAD §3: route dictionary lookup
    # -------------------------------------------------------------------------

    def test_find_route_returns_auth_entry_for_auth_path(self):
        # Arrange
        path = "/auth/login"
        # Act
        result = self.registry.find_route(path)
        # Assert
        assert result is not None
        assert result.prefix == "/auth"

    def test_find_route_returns_none_for_unknown_path(self):
        # Arrange
        path = "/unknown/endpoint"
        # Act
        result = self.registry.find_route(path)
        # Assert
        assert result is None

    def test_find_route_matches_vehiculos(self):
        # Arrange
        path = f"{settings.vehicles_service_prefix}/abc-123"
        # Act
        result = self.registry.find_route(path)
        # Assert
        assert result is not None
        assert result.prefix == settings.vehicles_service_prefix

    def test_find_route_matches_asignaciones(self):
        # Arrange
        path = f"{settings.assignments_service_prefix}/456"
        # Act
        result = self.registry.find_route(path)
        # Assert
        assert result is not None
        assert result.prefix == settings.assignments_service_prefix

    def test_find_route_matches_incidentes(self):
        # Arrange
        path = f"{settings.incidents_service_prefix}/789/detail"
        # Act
        result = self.registry.find_route(path)
        # Assert
        assert result is not None
        assert result.prefix == settings.incidents_service_prefix

    def test_find_route_matches_mantenimiento(self):
        # Arrange
        path = f"{settings.maintenance_service_prefix}/schedule"
        # Act
        result = self.registry.find_route(path)
        # Assert
        assert result is not None
        assert result.prefix == settings.maintenance_service_prefix

    def test_find_route_matches_reportes(self):
        # Arrange
        path = f"{settings.reports_service_prefix}/strategic/q1"
        # Act
        result = self.registry.find_route(path)
        # Assert
        assert result is not None
        assert result.prefix == settings.reports_service_prefix

    # -------------------------------------------------------------------------
    # Role configuration — SAD §1: each route has the correct allowed roles
    # -------------------------------------------------------------------------

    def test_auth_route_is_public(self):
        # Act
        route = self.registry.find_route("/auth/register")
        # Assert
        assert route is not None
        assert route.is_public() is True

    def test_vehiculos_allows_administrador(self):
        # Act
        route = self.registry.find_route(settings.vehicles_service_prefix)
        # Assert
        assert route is not None
        assert route.allows_role(Role.ADMINISTRADOR.value) is True

    def test_vehiculos_allows_empleado_mantenimiento(self):
        # Act
        route = self.registry.find_route(settings.vehicles_service_prefix)
        # Assert
        assert route is not None
        assert route.allows_role(Role.EMPLEADO_MANTENIMIENTO.value) is True

    def test_vehiculos_allows_empleado_incidentes(self):
        # Act
        route = self.registry.find_route(settings.vehicles_service_prefix)
        # Assert
        assert route is not None
        assert route.allows_role(Role.EMPLEADO_INCIDENTES.value) is True

    def test_vehiculos_denies_empleado_basic(self):
        # Arrange — SAD §1: basic EMPLEADO cannot access vehicles directly
        route = self.registry.find_route(settings.vehicles_service_prefix)
        # Assert
        assert route is not None
        assert route.allows_role(Role.EMPLEADO.value) is False

    def test_asignaciones_allows_empleado(self):
        # SAD §1: EMPLEADO accesses their own assignments
        route = self.registry.find_route(settings.assignments_service_prefix)
        assert route is not None
        assert route.allows_role(Role.EMPLEADO.value) is True

    def test_asignaciones_denies_empleado_mantenimiento(self):
        route = self.registry.find_route(settings.assignments_service_prefix)
        assert route is not None
        assert route.allows_role(Role.EMPLEADO_MANTENIMIENTO.value) is False

    def test_reportes_allows_only_administrador(self):
        # SAD §1: only ADMINISTRADOR generates strategic reports
        route = self.registry.find_route(settings.reports_service_prefix)
        assert route is not None
        assert route.allows_role(Role.ADMINISTRADOR.value) is True
        assert route.allows_role(Role.EMPLEADO.value) is False
        assert route.allows_role(Role.EMPLEADO_MANTENIMIENTO.value) is False
        assert route.allows_role(Role.EMPLEADO_INCIDENTES.value) is False

    def test_incidentes_allows_empleado_incidentes(self):
        route = self.registry.find_route(settings.incidents_service_prefix)
        assert route is not None
        assert route.allows_role(Role.EMPLEADO_INCIDENTES.value) is True

    def test_incidentes_denies_empleado_mantenimiento(self):
        route = self.registry.find_route(settings.incidents_service_prefix)
        assert route is not None
        assert route.allows_role(Role.EMPLEADO_MANTENIMIENTO.value) is False

    def test_mantenimiento_allows_empleado_mantenimiento(self):
        route = self.registry.find_route(settings.maintenance_service_prefix)
        assert route is not None
        assert route.allows_role(Role.EMPLEADO_MANTENIMIENTO.value) is True

    def test_mantenimiento_denies_empleado_incidentes(self):
        route = self.registry.find_route(settings.maintenance_service_prefix)
        assert route is not None
        assert route.allows_role(Role.EMPLEADO_INCIDENTES.value) is False

    # -------------------------------------------------------------------------
    # get_all_routes
    # -------------------------------------------------------------------------

    def test_get_all_routes_returns_list(self):
        # Act
        routes = self.registry.get_all_routes()
        # Assert
        assert isinstance(routes, list)
        assert len(routes) > 0

    def test_get_all_routes_returns_copy(self):
        # Arrange — modifying the returned list should not affect the registry
        routes = self.registry.get_all_routes()
        original_count = len(routes)
        # Act
        routes.clear()
        # Assert
        assert len(self.registry.get_all_routes()) == original_count

    def test_all_registered_prefixes_are_unique(self):
        # Arrange
        routes = self.registry.get_all_routes()
        prefixes = [r.prefix for r in routes]
        # Assert
        assert len(prefixes) == len(set(prefixes)), "Duplicate prefixes in route registry"
