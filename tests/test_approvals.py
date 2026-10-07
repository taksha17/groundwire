from uuid import UUID

from groundwire.enums import RunStatus
from groundwire.services.runs import get_run


async def _register_and_start(client, payload=None):
    agent = (
        await client.post(
            "/v1/agents",
            json={
                "name": "demo-ops-agent",
                "allowed_tools": ["send_email"],
                "approval_policy": {"require_approval_for": ["send_email"]},
            },
        )
    ).json()
    run = (
        await client.post(
            "/v1/runs",
            json={
                "agent_id": agent["id"],
                "payload": payload
                or {"to": "ops@example.com", "subject": "Outage", "body": "Please page on-call."},
            },
        )
    ).json()
    return agent, run


async def _set_status(session_factory, run_id: str, status: str) -> None:
    async with session_factory() as session:
        run = await get_run(session, UUID(run_id))
        assert run is not None
        run.status = status
        await session.commit()


async def test_approve_signals_temporal(client, fake_temporal, session_factory):
    _, run = await _register_and_start(client)
    await _set_status(session_factory, run["id"], RunStatus.AWAITING_APPROVAL)
    response = await client.post(
        f"/v1/runs/{run['id']}/approvals",
        json={"decision": "approve", "actor": "alice"},
    )
    assert response.status_code == 200
    assert fake_temporal.signals[-1].decision == "approve"
    assert fake_temporal.signals[-1].actor == "alice"


async def test_approve_when_not_waiting_returns_409(client):
    _, run = await _register_and_start(client)
    response = await client.post(
        f"/v1/runs/{run['id']}/approvals",
        json={"decision": "approve"},
    )
    assert response.status_code == 409


async def test_list_pending_approvals(client, session_factory):
    _, waiting = await _register_and_start(client)
    _, planning = await _register_and_start(
        client,
        payload={"to": "other@example.com", "subject": "Other", "body": "x"},
    )
    await _set_status(session_factory, waiting["id"], RunStatus.AWAITING_APPROVAL)
    response = await client.get("/v1/runs", params={"status": "awaiting_approval"})
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert waiting["id"] in ids
    assert planning["id"] not in ids
