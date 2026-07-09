"""
conftest.py — API Gateway test configuration
==============================================
Sets all required environment variables BEFORE any app module is imported.

JWT: the Gateway only ever needs the PUBLIC key (RS256) — it verifies tokens
signed elsewhere (auth_service), it never signs them. The ephemeral private
key generated here exists purely so tests can mint tokens that simulate what
auth_service would issue; GatewaySettings itself never references it.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared_testing.rsa_keys import generate_rsa_keypair, write_pem  # noqa: E402

_tmp_dir = tempfile.mkdtemp(prefix="fleetops_gateway_test_jwt_")

_TEST_PRIVATE_KEY, _TEST_PUBLIC_KEY = generate_rsa_keypair()
_WRONG_PRIVATE_KEY, _ = generate_rsa_keypair()  # simulates an attacker's own key pair

_public_key_path = write_pem(_TEST_PUBLIC_KEY, os.path.join(_tmp_dir, "jwt_public.pem"))

os.environ.setdefault("JWT_PUBLIC_KEY_PATH", _public_key_path)
os.environ.setdefault("JWT_ALGORITHM", "RS256")
os.environ.setdefault("AUTH_SERVICE_URL", "http://auth_service_test:8001")
os.environ.setdefault("ROLE_SERVICE_URL", "http://role_service_test:8002")
os.environ.setdefault("GATEWAY_RATE_LIMIT", "60")
os.environ.setdefault("GATEWAY_PORT", "8000")
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("LOG_LEVEL", "WARNING")


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
