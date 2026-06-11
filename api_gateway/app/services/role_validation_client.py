"""
API Gateway — Role Validation Client (Application/Service Layer)
=================================================================
SAD Reference: Proceso de validación y redirección (pág. 10):
  "El Gateway extrae la identidad del usuario.
   El servicio de roles verifica permisos."
Pattern: Service Client (anti-corruption layer toward RoleService)

This client is an application-layer adapter: it calls the RoleService
over HTTP. It is separated from the domain to keep RBACPolicy pure and
infrastructure-independent.

Note: The Gateway performs its own RBAC check via RBACPolicy (domain-level,
using the route registry). This client is used for an optional secondary
confirmation from the RoleService, consistent with the SAD flow diagram (pág. 10).
"""

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class RoleValidationClient:
    """
    HTTP client that calls the RoleService to validate a user's role.
    SAD §3/10: Gateway delegates role verification to the RoleService.
    """

    def __init__(self, base_url: Optional[str] = None) -> None:
        self._base_url = base_url or settings.role_service_url

    async def validate_role(
        self,
        user_id: str,
        required_roles: list[str],
    ) -> bool:
        """
        Calls RoleService to confirm the user has one of the required roles.

        Args:
            user_id:        The user's UUID from the JWT claims.
            required_roles: List of role strings that would grant access.

        Returns:
            True if the RoleService confirms authorization, False otherwise.
            On connection error: returns False (fail-closed — safer default).
        """
        url = f"{self._base_url}/roles/validate"
        payload = {
            "user_id": user_id,
            "required_roles": required_roles,
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(url, json=payload)

            if response.status_code == 200:
                data = response.json()
                authorized: bool = data.get("authorized", False)
                logger.info(
                    "RoleService validation | user_id=%s | authorized=%s",
                    user_id,
                    authorized,
                )
                return authorized

            logger.warning(
                "RoleService returned non-200 | status=%s | user_id=%s",
                response.status_code,
                user_id,
            )
            return False

        except httpx.RequestError as exc:
            logger.error(
                "RoleService unreachable | user_id=%s | error=%s",
                user_id,
                str(exc),
            )
            # SAD §3: Fiabilidad — Tolerancia de fallos
            # Fail closed: deny access when the role service is unavailable
            return False
