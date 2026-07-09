import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from app.routes.proxy_routes import router
from app.middleware.jwt_middleware import get_optional_jwt_claims, JWTClaims
from app.config import settings

# 1. Configurar una app de pruebas dedicada para aislar el router de proxy
app = FastAPI()
app.include_router(router)


# Mock de claims por defecto (Simula usuario Anónimo)
def mock_get_optional_jwt_claims_anonymous():
    return None


# Mock de claims para un Administrador válido
def mock_get_optional_jwt_claims_admin():
    return JWTClaims(user_id="user-123", role="ADMINISTRADOR", email="admin@fleetops.com")


@pytest.fixture
def client():
    """Cliente de pruebas por defecto (Anónimo)."""
    app.dependency_overrides[get_optional_jwt_claims] = mock_get_optional_jwt_claims_anonymous
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def client_admin():
    """Cliente de pruebas autenticado como ADMINISTRADOR."""
    app.dependency_overrides[get_optional_jwt_claims] = mock_get_optional_jwt_claims_admin
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# =============================================================================
# TESTS PARA PROXY_ROUTES
# =============================================================================


def test_proxy_route_not_found(client):
    """SAD §3: Si la ruta no existe en el diccionario, debe retornar 404."""
    # Act
    response = client.get("/invalid/route/prefix")

    # Assert
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "The requested resource does not exist."


def test_proxy_route_requires_auth(client):
    """SAD §3: Si la ruta es protegida y no hay JWT, debe retornar 401."""
    # Intentamos acceder a vehículos (que requiere rol) siendo anónimos
    target_path = f"{settings.vehicles_service_prefix}/abc-123"

    # Act
    response = client.get(target_path)

    # Assert
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Authentication required."


@pytest.mark.asyncio
async def test_proxy_success_forwarding(client_admin, httpx_mock):
    """SAD §3: Si el rol es correcto, reenvía la petición al microservicio."""
    # Arrange
    vehicles_prefix = settings.vehicles_service_prefix  # Ej: /api/vehicles
    target_path = f"{vehicles_prefix}/abc-123"
    upstream_target_url = f"{settings.vehicles_service_url}{target_path}"

    # Mockear la respuesta del microservicio destino usando `httpx_mock`
    httpx_mock.add_response(
        method="GET",
        url=upstream_target_url,
        status_code=200,
        content=b'{"id": "abc-123", "status": "active"}',
        headers={"content-type": "application/json"},
    )

    # Act
    response = client_admin.get(target_path)

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"id": "abc-123", "status": "active"}

    # Verificar que se inyectaron las cabeceras de identidad (Accountability SAD §4)
    request_headers = httpx_mock.get_request().headers
    assert request_headers["X-User-Id"] == "user-123"
    assert request_headers["X-User-Role"] == "ADMINISTRADOR"


@pytest.mark.asyncio
async def test_proxy_upstream_unreachable(client_admin, httpx_mock):
    """Verifica que si el microservicio destino está caído, devuelve un 503."""
    # Arrange
    vehicles_prefix = settings.vehicles_service_prefix
    target_path = f"{vehicles_prefix}/abc-123"
    upstream_target_url = f"{settings.vehicles_service_url}{target_path}"

    # Forzar un error de conexión en httpx
    import httpx

    httpx_mock.add_exception(httpx.ConnectError("Network unreachable"), url=upstream_target_url)

    # Act
    response = client_admin.get(target_path)

    # Assert
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["detail"] == "The requested service is temporarily unavailable."
