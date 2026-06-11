"""
Role Service — RoleDomainService (Domain Layer)
================================================
SAD Reference: <<Domain>> Role Service — "RBAC logic" (pág. 5)
               Proceso de validación y redirección (pág. 10):
               "El servicio de roles verifica permisos."
               "consultarRol() → rolEnCache()"
Pattern: Domain Service (DDD)
"""

from __future__ import annotations

from typing import Protocol

from app.domain.role import Role, UserRoleAssignment

# ---------------------------------------------------------------------------
# Infrastructure ports
# ---------------------------------------------------------------------------

class RoleRepository(Protocol):
    async def find_role_by_name(self, name: str) -> Role | None: ...
    async def find_roles_by_user_id(self, user_id: str) -> list[UserRoleAssignment]: ...
    async def save_role(self, role: Role) -> Role: ...
    async def assign_role_to_user(self, assignment: UserRoleAssignment) -> UserRoleAssignment: ...
    async def remove_role_from_user(self, user_id: str, role_name: str) -> bool: ...
    async def role_exists_by_name(self, name: str) -> bool: ...


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------

class RoleNotFoundError(Exception):
    pass


class RoleAssignmentError(Exception):
    pass


# ---------------------------------------------------------------------------
# Domain Service
# ---------------------------------------------------------------------------

class RoleDomainService:
    """
    Implements RBAC logic: role assignment, verification, and invalidation.
    SAD §4: RBAC — "Crear · Consultar · Modificar · Inhabilitar roles"
    """

    def __init__(self, role_repository: RoleRepository) -> None:
        self._repo = role_repository

    async def get_user_roles(self, user_id: str) -> list[str]:
        """
        Returns the list of role names for a user.
        SAD pág. 10: consultarRol() — called after rolEnCache() miss.
        """
        assignments = await self._repo.find_roles_by_user_id(user_id)
        return [a.role_name for a in assignments]

    async def validate_user_has_any_role(
        self,
        user_id: str,
        required_roles: list[str],
    ) -> bool:
        """
        Validates whether the user holds at least one of the required roles.
        SAD pág. 10 flow: returns the authorization decision.

        Args:
            user_id:        The user's UUID.
            required_roles: Role names that would grant access.

        Returns:
            True if user has at least one matching role, False otherwise.
        """
        if not required_roles:
            return True  # No restriction means public access

        user_roles = await self.get_user_roles(user_id)
        required_upper = {r.upper() for r in required_roles}
        return bool(set(user_roles) & required_upper)

    async def assign_role(
        self,
        user_id: str,
        role_name: str,
        assigned_by: str | None = None,
    ) -> UserRoleAssignment:
        """
        Assigns a role to a user.
        SAD §3: only administrators can assign roles.
        The caller (API layer) must verify the requester is ADMINISTRADOR.

        Raises:
            RoleNotFoundError: if the role does not exist in the catalog.
            RoleAssignmentError: if the user already holds this role.
        """
        role = await self._repo.find_role_by_name(role_name.upper())
        if role is None:
            raise RoleNotFoundError(f"Role '{role_name}' does not exist in the system.")

        if not role.is_active:
            raise RoleAssignmentError(f"Role '{role_name}' is currently disabled.")

        assignment = UserRoleAssignment.create(
            user_id=user_id,
            role_id=role.id,
            role_name=role.name,
            assigned_by=assigned_by,
        )
        return await self._repo.assign_role_to_user(assignment)

    async def remove_role(self, user_id: str, role_name: str) -> bool:
        """
        Removes a role from a user.
        SAD §4: administrators can modify role assignments.
        """
        removed = await self._repo.remove_role_from_user(user_id, role_name.upper())
        if not removed:
            raise RoleNotFoundError(
                f"User '{user_id}' does not have role '{role_name}'."
            )
        return True
