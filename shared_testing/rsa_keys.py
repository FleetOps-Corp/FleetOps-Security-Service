"""
shared_testing/rsa_keys.py — Ephemeral RSA key pair generation for tests
==========================================================================
Shared by auth_service and api_gateway test suites to avoid duplicating
the RSA key generation / temp-file-writing logic (SonarCloud DRY compliance).

auth_service uses both keys (it signs and verifies tokens).
api_gateway uses only the public key in production but needs the private
key in tests to mint sample tokens that simulate what auth_service issues.
"""

import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_rsa_keypair() -> tuple[str, str]:
    """Generates an ephemeral RSA key pair, returns (private_pem, public_pem)."""
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


def write_pem(content: str, path: str) -> str:
    """Writes PEM content to path, returns the path (convenience for chaining)."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path