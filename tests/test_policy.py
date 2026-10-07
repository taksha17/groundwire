from uuid import UUID

from groundwire.enums import RunStatus
from groundwire.services.runs import get_run
from tests.conftest import AGENT_BODY, TENANT_A, auth_headers
from tests.jwt_util import mint_token


async def test_operator_cannot_register_agents(auth_client, rsa_keys):
    private_pem, _ = rsa_keys
    token = mint_token(
        private_pem,
        sub="op-1",
        username="operator",
        tenant_id=TENANT_A,
        roles=["groundwire-operator"],
    )
    response = await auth_client.post("/v1/agents", json=AGENT_BODY, headers=auth_headers(token))
    assert response.status_code == 403


async def test_operator_can_approve_and_actor_is_username(
    auth_client, rsa_keys, fake_temporal, session_factory
):
    private_pem, _ = rsa_keys
    admin = mint_token(
        private_pem,
        sub="admin-1",
        username="admin",
        tenant_id=TENANT_A,
        roles=["groundwire-admin"],
    )
    operator = mint_token(
        private_pem,
        sub="op-1",
        username="operator",
        tenant_id=TENANT_A,
        roles=["groundwire-operator"],
    )
    agent = (
        await auth_client.post("/v1/agents", json=AGENT_BODY, headers=auth_headers(admin))
    ).json()
    run = (
        await auth_client.post(
            "/v1/runs",
            json={
                "agent_id": agent["id"],
                "payload": {"to": "ops@example.com", "subject": "Outage", "body": "x"},
            },
            headers=auth_headers(admin),
        )
    ).json()
    async with session_factory() as session:
        db_run = await get_run(session, UUID(run["id"]))
        assert db_run is not None
        db_run.status = RunStatus.AWAITING_APPROVAL
        db_run.pending_action = {
            "tool": "send_email",
            "params": {"to": "ops@example.com"},
            "rationale": "Notify ops",
        }
        await session.commit()

    response = await auth_client.post(
        f"/v1/runs/{run['id']}/approvals",
        json={"decision": "approve", "actor": "spoofed"},
        headers=auth_headers(operator),
    )
    assert response.status_code == 200
    assert fake_temporal.signals[-1].actor == "operator"
