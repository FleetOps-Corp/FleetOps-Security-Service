"""
API Gateway — Auth Routes (API Layer)
======================================
SAD Reference: "POST /register · POST /login" (pág. 5 diagram)
               "El usuario se loguea, a través del authservice y obtiene su token" (§3)
               Public routes — no authentication or RBAC check required.

These routes proxy requests transparently to the AuthService.
The Gateway adds no auth logic here — the AuthService owns that responsibility.
"""

import logging

import httpx
from fastapi import APIRouter, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])
limiter = Limiter(key_func=get_remote_address)


async def _proxy_to_auth(request: Request, path: str) -> Response:
    """
    Generic proxy helper: forwards the incoming request to the AuthService
    and returns its response verbatim.

    Args:
        request: The incoming FastAPI request.
        path:    The path suffix to append to the AuthService base URL.

    Returns:
        The upstream response as a FastAPI Response.
    """
    target_url = f"{settings.auth_service_url}{path}"
    body = await request.body()
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length")
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            upstream = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )

        logger.info(
            "Proxied auth request | path=%s | upstream_status=%s",
            path,
            upstream.status_code,
        )

        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers=dict(upstream.headers),
            media_type=upstream.headers.get("content-type"),
        )

    except httpx.RequestError as exc:
        logger.error("AuthService unreachable | path=%s | error=%s", path, str(exc))
        return Response(
            content=b'{"error": "auth_service_unavailable", "detail": "Authentication service is temporarily unavailable."}',
            status_code=503,
            media_type="application/json",
        )


@router.post("/register")
async def register(request: Request) -> Response:
    """
    Proxy: POST /auth/register → AuthService POST /register
    SAD §3: Public entry point for new user registration.
    Roles are NOT assigned here — administrators assign roles (SAD §3).
    """
    return await _proxy_to_auth(request, "/register")


@router.post("/login")
async def login(request: Request) -> Response:
    """
    Proxy: POST /auth/login → AuthService POST /login
    SAD §3 flow step 1-6: User sends credentials, gets JWT back.
    """
    return await _proxy_to_auth(request, "/login")
