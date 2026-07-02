"""
API Gateway — RBAC Policy (Domain Layer)
=========================================
SAD Reference: "control de acceso basado en roles RBAC" (§4, §7)
Pattern: Policy Object (GoF variant) — encapsulates authorization decision

This module is responsible for the single question:
  "Is this user's role allowed to access this route?"

It depends ONLY on the RouteRegistry (domain-to-domain dependency).
It has zero infrastructure dependencies — making it fully unit-testable.
"""

from dataclasses import dataclass

from app.domain.route_registry import RouteEntry, RouteRegistry


@dataclass(frozen=True)
class AuthorizationResult:
    """
    Value object representing the outcome of an RBAC authorization check.

    Attributes:
        authorized:   True if access is granted.
        reason:       Human-readable explanation (logged for accountability — SAD §4).
        route_entry:  The matched route (None if route not found).
    """

    authorized: bool
    reason: str
    route_entry: RouteEntry | None = None


class RBACPolicy:
    """
    Domain service implementing the RBAC authorization policy.
    SAD Reference: "mecanismo de autorización" (§7), RBAC (§1, §4)

    Decision logic (SAD §3 flow, step 3):
      1. Find the route in the registry.
      2. If route not found → DENY (404-equivalent at gateway level).
      3. If route is public → ALLOW unconditionally.
      4. If no user role provided → DENY (unauthenticated).
      5. If user role is in allowed_roles → ALLOW.
      6. Otherwise → DENY (insufficient permissions).
    """

    def __init__(self, registry: RouteRegistry) -> None:
        self._registry = registry

    def evaluate(self, path: str, user_role: str | None) -> AuthorizationResult:
        """
        Evaluates whether the request is authorized.

        Args:
            path:       The full request path (e.g. "/vehiculos/abc/123")
            user_role:  The role extracted from the validated JWT, or None
                        if the request carries no token.

        Returns:
            AuthorizationResult with authorized=True/False and a reason string.
        """
        route = self._registry.find_route(path)

        if route is None:
            return AuthorizationResult(
                authorized=False,
                reason=f"No route registered for path: {path}",
                route_entry=None,
            )

        if route.is_public():
            return AuthorizationResult(
                authorized=True,
                reason="Public route — no authentication required",
                route_entry=route,
            )

        if user_role is None:
            return AuthorizationResult(
                authorized=False,
                reason="Authentication required — no token provided",
                route_entry=route,
            )

        if route.allows_role(user_role):
            return AuthorizationResult(
                authorized=True,
                reason=f"Role '{user_role}' is authorized for route '{route.prefix}'",
                route_entry=route,
            )

        return AuthorizationResult(
            authorized=False,
            reason=(
                f"Role '{user_role}' is not permitted for route '{route.prefix}'. "
                f"Allowed roles: {[r.value for r in route.allowed_roles]}"
            ),
            route_entry=route,
        )
