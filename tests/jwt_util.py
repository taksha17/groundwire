from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER = "http://test/realms/groundwire"
AUDIENCE = "groundwire-api"


def generate_rsa_pem() -> tuple[bytes, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def mint_token(
    private_pem: bytes,
    *,
    sub: str,
    username: str,
    tenant_id: UUID,
    roles: list[str],
) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": sub,
            "preferred_username": username,
            "tenant_id": str(tenant_id),
            "realm_access": {"roles": roles},
            "aud": [AUDIENCE, "account"],
            "iss": ISSUER,
            "iat": now,
            "exp": now + timedelta(hours=1),
        },
        private_pem,
        algorithm="RS256",
    )
