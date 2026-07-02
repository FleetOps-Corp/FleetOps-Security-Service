"""
Unit Tests — RBACPolicy (Domain Layer)
========================================
Coverage target: 100% of RBACPolicy public methods.
Pattern: AAA (Arrange → Act → Assert)
SAD Reference: RBAC (§1, §4, §7), authorization decision logic

All infrastructure is absent — pure domain logic only.
"""

import pytest

from app.domain.rbac_policy import AuthorizationResult, RBACPolicy
from app.domain.route_registry import Role, RouteRegistry


@pytest.fixture
def registry() -> RouteRegistry:
    """Shared real RouteRegistry instance (domain-only, no DB)."""
    return RouteRegistry()


@pytest.fixture
def policy(registry: RouteRegistry) -> RBACPolicy:
    """Shared RBACPolicy bound to the real registry."""
    return RBACPolicy(registry)


# =============================================================================
# AuthorizationResult value object tests
# =============================================================================


class TestAuthorizationResult:
    def test_authorized_result_has_correct_flags(self):
        # Arrange & Act
        result = AuthorizationResult(authorized=True, reason="ok")
        # Assert
        assert result.authorized is True
        assert result.reason == "ok"
        assert result.route_entry is None

    def test_unauthorized_result_has_correct_flags(self):
        # Arrange & Act
        result = AuthorizationResult(authorized=False, reason="denied")
        # Assert
        assert result.authorized is False


# =============================================================================
# RBACPolicy.evaluate — all branches
# =============================================================================


class TestRBACPolicyEvaluate:
    # -------------------------------------------------------------------------
    # Branch 1: Route not found
    # -------------------------------------------------------------------------

    def test_evaluate_denies_unknown_route(self, policy: RBACPolicy):
        # Arrange
        path = "/nonexistent/resource"
        # Act
        result = policy.evaluate(path=path, user_role="ADMINISTRADOR")
        # Assert
        assert result.authorized is False
        assert "No route registered" in result.reason
        assert result.route_entry is None

    def test_evaluate_unknown_route_returns_none_entry(self, policy: RBACPolicy):
        # Act
        result = policy.evaluate(path="/does/not/exist", user_role=None)
        # Assert
        assert result.route_entry is None

    # -------------------------------------------------------------------------
    # Branch 2: Public routes — always authorized regardless of role
    # -------------------------------------------------------------------------

    def test_evaluate_public_route_with_no_token(self, policy: RBACPolicy):
        # Arrange — /auth is public (SAD §3: login/register accessible without token)
        path = "/auth/login"
        # Act
        result = policy.evaluate(path=path, user_role=None)
        # Assert
        assert result.authorized is True
        assert "Public route" in result.reason

    def test_evaluate_public_route_with_any_role(self, policy: RBACPolicy):
        # Arrange
        path = "/auth/register"
        # Act
        result = policy.evaluate(path=path, user_role=Role.EMPLEADO.value)
        # Assert
        assert result.authorized is True

    # -------------------------------------------------------------------------
    # Branch 3: Protected route with no role (unauthenticated)
    # -------------------------------------------------------------------------

    def test_evaluate_protected_route_with_no_token_is_denied(self, policy: RBACPolicy):
        # Arrange — /vehiculos requires at least EMPLEADO_MANTENIMIENTO
        path = "/vehiculos/123"
        # Act
        result = policy.evaluate(path=path, user_role=None)
        # Assert
        assert result.authorized is False
        assert "Authentication required" in result.reason

    def test_evaluate_protected_route_with_none_role_returns_route_entry(self, policy: RBACPolicy):
        # Act
        result = policy.evaluate(path="/reportes/q1", user_role=None)
        # Assert — route_entry is returned even when denied, for error handling
        assert result.route_entry is not None
        assert result.route_entry.prefix == "/reportes"

    # -------------------------------------------------------------------------
    # Branch 4: Role IS in allowed_roles → authorized
    # -------------------------------------------------------------------------

    def test_evaluate_administrador_can_access_vehiculos(self, policy: RBACPolicy):
        # Arrange
        path = "/vehiculos/fleet-001"
        # Act
        result = policy.evaluate(path=path, user_role=Role.ADMINISTRADOR.value)
        # Assert
        assert result.authorized is True

    def test_evaluate_empleado_mantenimiento_can_access_vehiculos(self, policy: RBACPolicy):
        # Arrange — SAD §1: maintenance employee accesses vehicle info
        path = "/vehiculos/engine-data"
        # Act
        result = policy.evaluate(path=path, user_role=Role.EMPLEADO_MANTENIMIENTO.value)
        # Assert
        assert result.authorized is True

    def test_evaluate_empleado_can_access_asignaciones(self, policy: RBACPolicy):
        # Arrange — SAD §1: basic employee accesses their assignments
        path = "/asignaciones/my-route"
        # Act
        result = policy.evaluate(path=path, user_role=Role.EMPLEADO.value)
        # Assert
        assert result.authorized is True

    def test_evaluate_empleado_incidentes_can_access_incidentes(self, policy: RBACPolicy):
        # Act
        result = policy.evaluate(
            path="/incidentes/incident-007",
            user_role=Role.EMPLEADO_INCIDENTES.value,
        )
        # Assert
        assert result.authorized is True

    def test_evaluate_empleado_mantenimiento_can_access_mantenimiento(self, policy: RBACPolicy):
        # Act
        result = policy.evaluate(
            path="/mantenimiento/preventive/schedule",
            user_role=Role.EMPLEADO_MANTENIMIENTO.value,
        )
        # Assert
        assert result.authorized is True

    def test_evaluate_administrador_can_access_reportes(self, policy: RBACPolicy):
        # Arrange — SAD §1: admin generates strategic reports
        path = "/reportes/q1-strategic"
        # Act
        result = policy.evaluate(path=path, user_role=Role.ADMINISTRADOR.value)
        # Assert
        assert result.authorized is True

    # -------------------------------------------------------------------------
    # Branch 5: Role is NOT in allowed_roles → denied (wrong role)
    # -------------------------------------------------------------------------

    def test_evaluate_empleado_cannot_access_vehiculos(self, policy: RBACPolicy):
        # Arrange — SAD §1: basic employee has no vehicle access
        path = "/vehiculos/full-list"
        # Act
        result = policy.evaluate(path=path, user_role=Role.EMPLEADO.value)
        # Assert
        assert result.authorized is False
        assert "not permitted" in result.reason

    def test_evaluate_empleado_cannot_access_reportes(self, policy: RBACPolicy):
        # Act
        result = policy.evaluate(
            path="/reportes/annual",
            user_role=Role.EMPLEADO.value,
        )
        # Assert
        assert result.authorized is False

    def test_evaluate_empleado_mantenimiento_cannot_access_incidentes(self, policy: RBACPolicy):
        # Arrange — maintenance employee cannot manage incidents
        result = policy.evaluate(
            path="/incidentes/list",
            user_role=Role.EMPLEADO_MANTENIMIENTO.value,
        )
        # Assert
        assert result.authorized is False

    def test_evaluate_empleado_incidentes_cannot_access_mantenimiento(self, policy: RBACPolicy):
        result = policy.evaluate(
            path="/mantenimiento/history",
            user_role=Role.EMPLEADO_INCIDENTES.value,
        )
        assert result.authorized is False

    def test_evaluate_denied_result_includes_route_entry(self, policy: RBACPolicy):
        # Arrange — ensure route_entry is present even on role-mismatch denial
        result = policy.evaluate(
            path="/reportes/q4",
            user_role=Role.EMPLEADO.value,
        )
        # Assert
        assert result.route_entry is not None
        assert result.route_entry.prefix == "/reportes"

    def test_evaluate_denial_reason_mentions_role_and_route(self, policy: RBACPolicy):
        # Arrange
        role = Role.EMPLEADO.value
        path = "/reportes/strategic"
        # Act
        result = policy.evaluate(path=path, user_role=role)
        # Assert — reason should mention the role for accountability (SAD §4)
        assert role in result.reason
        assert "/reportes" in result.reason

    def test_evaluate_unknown_role_string_is_denied(self, policy: RBACPolicy):
        # Arrange — a role that doesn't exist in the system should be denied
        result = policy.evaluate(
            path="/vehiculos/list",
            user_role="SUPER_VILLAIN",
        )
        # Assert
        assert result.authorized is False
