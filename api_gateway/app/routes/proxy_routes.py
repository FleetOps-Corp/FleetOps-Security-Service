"""
API Gateway — Proxy Routes (API Layer)
========================================
SAD Reference: Proceso de validación y redirección (pág. 10)
  1. Client sends request with JWT.
  2. Gateway extracts user identity.
  3. Role service verifies permissions.
  4. Roles checked in Redis first, then PostgreSQL.
  5. Authorization returned.
  6. Request redirected to corresponding microservice.

Pattern: API Gateway (EIP) — reverse proxy with JWT+RBAC enforcement
Tactic: CORS (SAD §6), Rate Limiting (SAD §6/7/8)

This single catch-all route handles ALL protected downstream microservices.
The route registry determines which service to forward to and which roles
are required. This avoids duplicating auth logic per service.
"""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.config import settings
from app.domain.rbac_policy import RBACPolicy
from app.domain.route_registry import RouteRegistry
from app.middleware.jwt_middleware import JWTClaims, get_optional_jwt_claims

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Proxy"])

# Shared domain instances (instantiated once at module load)
_registry = RouteRegistry()
_rbac = RBACPolicy(_registry)

# URL key → settings attribute mapping
_URL_KEY_MAP: dict[str, str] = {
    "auth_service_url": settings.auth_service_url,
    "role_service_url": settings.role_service_url,
    "vehicles_service_url": settings.vehicles_service_url,
    "assignments_service_url": settings.assignments_service_url,
    "incidents_service_url": settings.incidents_service_url,
    "maintenance_service_url": settings.maintenance_service_url,
    "reports_service_url": settings.reports_service_url,
}


def _resolve_upstream_url(url_key: str) -> str:
    """
    Resolves a settings key to an actual service URL.
    Raises HTTPException 503 if the key is unknown (misconfiguration guard).
    """
    url = _URL_KEY_MAP.get(url_key)
    if not url:
        logger.error("Unknown upstream URL key: %s", url_key)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gateway routing configuration error.",
        )
    return url


@router.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def proxy_request(
    full_path: str,
    request: Request,
    jwt_claims: Optional[JWTClaims] = Depends(get_optional_jwt_claims),
) -> Response:
    """
    Generic reverse proxy with JWT validation and RBAC enforcement.

    Flow (SAD §3 / pág. 10):
      1. Extract identity from JWT (handled by get_optional_jwt_claims).
      2. Evaluate RBAC policy against the route registry.
      3. If authorized, forward the request to the upstream microservice.
      4. Return the upstream response to the client.

    The downstream service URL and path are invisible to the client (SAD §3:
    "las rutas internas de los microservicios son invisibles al usuario").
    """
    path = f"/{full_path}"
    user_role = jwt_claims.role if jwt_claims else None
    user_id = jwt_claims.user_id if jwt_claims else "anonymous"

    # --- Step 2: RBAC evaluation (SAD pág. 10 — validarRol) ---
    decision = _rbac.evaluate(path=path, user_role=user_role)

    if not decision.authorized:
        logger.warning(
            "Access denied | user_id=%s | role=%s | path=%s | reason=%s",
            user_id,
            user_role,
            path,
            decision.reason,
        )

        # Distinguish between "not authenticated" and "wrong role"
        if user_role is None and decision.route_entry and not decision.route_entry.is_public():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if decision.route_entry is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The requested resource does not exist.",
            )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not have permission to access this resource.",
        )

    # --- Step 3: Resolve upstream URL (SAD §3: route dictionary) ---
    assert decision.route_entry is not None  # mypy type guard
    upstream_base = _resolve_upstream_url(decision.route_entry.upstream_url_key)
    target_url = f"{upstream_base}{path}"

    logger.info("Target URL: %s", target_url)

    logger.info(
        "Proxying request | user_id=%s | role=%s | path=%s → %s",
        user_id,
        user_role,
        path,
        upstream_base,
    )

    # --- Step 4: Forward request to upstream microservice ---
    body = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}

    # Inject identity headers for downstream microservices (SAD §4: accountability)
    if jwt_claims:
        headers["X-User-Id"] = jwt_claims.user_id
        headers["X-User-Role"] = jwt_claims.role
        headers["X-User-Email"] = jwt_claims.email

    logger.info(
        "Authorization header: %s",
        headers.get("authorization"),
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            upstream_response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                params=dict(request.query_params),
            )

        logger.info(
            "Upstream responded | path=%s | status=%s",
            path,
            upstream_response.status_code,
        )

        # Step 5: Return upstream response to client
        response_headers = {}

        logger.info("Upstream headers: %s", dict(upstream_response.headers))

        for header in (
            "content-type",
            "content-disposition",
            "cache-control",
            "etag",
            "last-modified",
            "content-encoding",
        ):
            if header in upstream_response.headers:
                response_headers[header] = upstream_response.headers[header]

        return Response(
            content=upstream_response.content,
            status_code=upstream_response.status_code,
            headers=response_headers,
        )

    except httpx.RequestError as exc:
        logger.error(
            "Upstream unreachable | path=%s | target=%s | error=%s",
            path,
            upstream_base,
            str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The requested service is temporarily unavailable.",
        )
