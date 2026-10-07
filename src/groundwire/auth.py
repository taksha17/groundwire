from uuid import UUID

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from groundwire.identity import Identity
from groundwire.settings import DEFAULT_TENANT_ID, Settings, get_settings

_bearer = HTTPBearer(auto_error=False)
_jwks_clients: dict[str, PyJWKClient] = {}

ANONYMOUS = Identity(
    subject="anonymous",
    username="anonymous",
    tenant_id=DEFAULT_TENANT_ID,
    roles=frozenset({"groundwire-admin"}),
)


def _jwks_client(url: str) -> PyJWKClient:
    client = _jwks_clients.get(url)
    if client is None:
        client = PyJWKClient(url)
        _jwks_clients[url] = client
    return client


def decode_access_token(token: str, settings: Settings) -> dict:
    options = {"verify_aud": True}
    if settings.oidc_public_key:
        return jwt.decode(
            token,
            settings.oidc_public_key,
            algorithms=["RS256"],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
            options=options,
        )
    jwks_url = settings.oidc_jwks_url or f"{settings.oidc_issuer}/protocol/openid-connect/certs"
    key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        key.key,
        algorithms=["RS256"],
        audience=settings.oidc_audience,
        issuer=settings.oidc_issuer,
        options=options,
    )


def identity_from_claims(claims: dict) -> Identity:
    tenant_raw = claims.get("tenant_id")
    if not tenant_raw:
        raise ValueError("tenant_id claim is required")
    realm_roles = claims.get("realm_access", {}).get("roles", [])
    username = claims.get("preferred_username") or claims.get("username") or str(claims.get("sub"))
    return Identity(
        subject=str(claims.get("sub") or username),
        username=str(username),
        tenant_id=UUID(str(tenant_raw)),
        roles=frozenset(str(role) for role in realm_roles),
    )


async def get_identity(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> Identity:
    if not settings.auth_enabled:
        return ANONYMOUS
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="not authenticated")
    try:
        claims = decode_access_token(creds.credentials, settings)
        identity = identity_from_claims(claims)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token") from None
    if not identity.can_operate():
        raise HTTPException(status_code=403, detail="insufficient role")
    return identity
