"""
conftest.py — Auth Service test configuration

Sets up environment variables required for AuthSettings() to load at import
time, and generates an ephemeral RSA key pair written to a temp directory
(since JWT_PRIVATE_KEY_PATH/JWT_PUBLIC_KEY_PATH are file paths read via
Settings properties, not raw string secrets like before).
"""

import os
import shutil
import tempfile

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_tmp_dir = tempfile.mkdtemp(prefix="fleetops_test_jwt_keys_")


def _generate_rsa_keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


_TEST_PRIVATE_KEY, _TEST_PUBLIC_KEY = _generate_rsa_keypair()
_WRONG_PRIVATE_KEY, _ = _generate_rsa_keypair()

_private_key_path = os.path.join(_tmp_dir, "jwt_private.pem")
_public_key_path = os.path.join(_tmp_dir, "jwt_public.pem")

with open(_private_key_path, "w", encoding="utf-8") as f:
    f.write(_TEST_PRIVATE_KEY)
with open(_public_key_path, "w", encoding="utf-8") as f:
    f.write(_TEST_PUBLIC_KEY)

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql+psycopg2://test:test@localhost:5432/test_db")
os.environ.setdefault("JWT_PRIVATE_KEY_PATH", _private_key_path)
os.environ.setdefault("JWT_PUBLIC_KEY_PATH", _public_key_path)
os.environ.setdefault("JWT_ALGORITHM", "RS256")
os.environ.setdefault("JWT_EXPIRATION_MINUTES", "60")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("LOG_LEVEL", "WARNING")


@pytest.fixture(scope="session")
def test_private_key() -> str:
    return _TEST_PRIVATE_KEY


@pytest.fixture(scope="session")
def test_public_key() -> str:
    return _TEST_PUBLIC_KEY


@pytest.fixture(scope="session")
def wrong_private_key() -> str:
    return _WRONG_PRIVATE_KEY


@pytest.fixture(scope="session", autouse=True)
def _cleanup_tmp_keys():
    yield
    shutil.rmtree(_tmp_dir, ignore_errors=True)