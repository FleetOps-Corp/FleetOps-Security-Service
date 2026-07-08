"""
conftest.py — API Gateway test configuration
==============================================
Sets all required environment variables BEFORE any app module is imported.
This is the correct pytest approach for services that use Pydantic Settings:
the production code remains clean (no Optional fields with None defaults for
truly required values), and tests supply safe test-only values.

JWT: the Gateway only ever needs the PUBLIC key (RS256) — it verifies tokens
signed elsewhere (auth_service), it never signs them. The ephemeral private
key generated here exists purely so tests can mint tokens that simulate what
auth_service would issue; GatewaySettings itself never references it.

[Archetype Convention Addition]
Justified by: pytest best practices for 12-factor apps (environment-based config).
"""

import os
import shutil
import tempfile

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# =============================================================================
# Ephemeral RSA key pair — public key written to disk (Settings reads a path),
# private key kept only in memory for tests that need to mint sample tokens.
# =============================================================================

_tmp_dir = tempfile.mkdtemp(prefix="fleetops_gateway_test_jwt_")


def _generate_rsa_keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


_TEST_PRIVATE_KEY, _TEST_PUBLIC_KEY = _generate_rsa_keypair()
_WRONG_PRIVATE_KEY, _ = _generate_rsa_keypair()  # simulates an attacker's own key pair

_public_key_path = os.path.join(_tmp_dir, "jwt_public.pem")
with open(_public_key_path, "w", encoding="utf-8") as f:
    f.write(_TEST_PUBLIC_KEY)

# =============================================================================
# Environment variables — must be set BEFORE any `app.*` module is imported,
# since `app.config.settings = GatewaySettings()` runs at import time.
# =============================================================================

os.environ.setdefault("JWT_PUBLIC_KEY_PATH", _public_key_path)
os.environ.setdefault("JWT_ALGORITHM", "RS256")
os.environ.setdefault("AUTH_SERVICE_URL", "http://auth_service_test:8001")
os.environ.setdefault("ROLE_SERVICE_URL", "http://role_service_test:8002")
os.environ.setdefault("GATEWAY_RATE_LIMIT", "60")
os.environ.setdefault("GATEWAY_PORT", "8000")
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("LOG_LEVEL", "WARNING")


# =============================================================================
# Fixtures — shared RSA material for tests that mint/verify sample tokens
# =============================================================================


@pytest.fixture(scope="session")
def test_private_key() -> str:
    """Simulates auth_service's private key — used ONLY to sign test tokens.
    GatewaySettings never has access to this in production."""
    return _TEST_PRIVATE_KEY


@pytest.fixture(scope="session")
def test_public_key() -> str:
    return _TEST_PUBLIC_KEY


@pytest.fixture(scope="session")
def wrong_private_key() -> str:
    """A private key from a DIFFERENT key pair — for tamper/forgery tests."""
    return _WRONG_PRIVATE_KEY


@pytest.fixture(scope="session", autouse=True)
def _cleanup_tmp_keys():
    yield
    shutil.rmtree(_tmp_dir, ignore_errors=True)
