from tests.conftest import AGENT_BODY, TENANT_A, TENANT_B, auth_headers
from tests.jwt_util import mint_token


async def test_missing_bearer_is_401_when_auth_enabled(auth_client):
    response = await auth_client.get("/v1/agents")
    assert response.status_code == 401


async def test_invalid_token_is_401(auth_client):
    response = await auth_client.get("/v1/agents", headers=auth_headers("not-a-jwt"))
    assert response.status_code == 401


async def test_valid_admin_token_can_register(auth_client, rsa_keys):
    private_pem, _ = rsa_keys
    token = mint_token(
        private_pem,
        sub="admin-1",
        username="admin",
        tenant_id=TENANT_A,
        roles=["groundwire-admin"],
    )
    response = await auth_client.post("/v1/agents", json=AGENT_BODY, headers=auth_headers(token))
    assert response.status_code == 201
    me = await auth_client.get("/v1/me", headers=auth_headers(token))
    assert me.status_code == 200
    body = me.json()
    assert body["username"] == "admin"
    assert "groundwire-admin" in body["roles"]


async def test_tenant_b_cannot_read_tenant_a_run(auth_client, rsa_keys):
    private_pem, _ = rsa_keys
    admin_a = mint_token(
        private_pem,
        sub="admin-a",
        username="admin-a",
        tenant_id=TENANT_A,
        roles=["groundwire-admin"],
    )
    admin_b = mint_token(
        private_pem,
        sub="admin-b",
        username="admin-b",
        tenant_id=TENANT_B,
        roles=["groundwire-admin"],
    )
    agent = (
        await auth_client.post("/v1/agents", json=AGENT_BODY, headers=auth_headers(admin_a))
    ).json()
    run = (
        await auth_client.post(
            "/v1/runs",
            json={"agent_id": agent["id"], "payload": {"to": "ops@example.com"}},
            headers=auth_headers(admin_a),
        )
    ).json()
    hidden = await auth_client.get(f"/v1/runs/{run['id']}", headers=auth_headers(admin_b))
    assert hidden.status_code == 404
    listed = await auth_client.get("/v1/runs", headers=auth_headers(admin_b))
    assert listed.status_code == 200
    assert listed.json() == []
