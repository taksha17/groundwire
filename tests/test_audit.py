from datetime import datetime, timedelta, timezone
from uuid import UUID

from groundwire.enums import RunStatus
from groundwire.models import AuditRecord
from groundwire.services.runs import get_run
from groundwire.settings import DEFAULT_TENANT_ID
from tests.conftest import AGENT_BODY, TENANT_A, TENANT_B, auth_headers
from tests.jwt_util import mint_token


async def _seed_run_with_audit(client, token, session_factory, *, actor="system"):
    agent = (await client.post("/v1/agents", json=AGENT_BODY, headers=auth_headers(token))).json()
    run = (
        await client.post(
            "/v1/runs",
            json={"agent_id": agent["id"], "payload": {"to": "ops@example.com"}},
            headers=auth_headers(token),
        )
    ).json()
    async with session_factory() as session:
        db_run = await get_run(session, UUID(run["id"]))
        assert db_run is not None
        db_run.status = RunStatus.COMPLETED
        session.add(
            AuditRecord(
                tenant_id=db_run.tenant_id,
                run_id=db_run.id,
                event_type="plan_completed",
                actor=actor,
                payload={"ok": True},
            )
        )
        session.add(
            AuditRecord(
                tenant_id=db_run.tenant_id,
                run_id=db_run.id,
                event_type="run_completed",
                actor=actor,
                payload={"status": "completed"},
            )
        )
        await session.commit()
    return agent, run


async def test_audit_query_filters_by_agent_and_outcome(auth_client, rsa_keys, session_factory):
    private_pem, _ = rsa_keys
    token = mint_token(
        private_pem,
        sub="admin-1",
        username="admin",
        tenant_id=TENANT_A,
        roles=["groundwire-admin"],
    )
    agent, run = await _seed_run_with_audit(auth_client, token, session_factory)
    response = await auth_client.get(
        "/v1/audit",
        params={"agent_id": agent["id"], "outcome": "completed"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    rows = response.json()
    assert {row["event_type"] for row in rows} == {"plan_completed", "run_completed"}
    assert all(row["run_id"] == run["id"] for row in rows)
    assert all(row["outcome"] == "completed" for row in rows)


async def test_audit_csv_matches_json(auth_client, rsa_keys, session_factory):
    private_pem, _ = rsa_keys
    token = mint_token(
        private_pem,
        sub="admin-1",
        username="admin",
        tenant_id=TENANT_A,
        roles=["groundwire-admin"],
    )
    await _seed_run_with_audit(auth_client, token, session_factory)
    json_rows = (await auth_client.get("/v1/audit", headers=auth_headers(token))).json()
    csv_response = await auth_client.get(
        "/v1/audit",
        params={"format": "csv"},
        headers=auth_headers(token),
    )
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
    text = csv_response.text
    assert "event_type" in text
    for row in json_rows:
        assert row["event_type"] in text
        assert row["run_id"] in text


async def test_run_audit_timeline(auth_client, rsa_keys, session_factory):
    private_pem, _ = rsa_keys
    token = mint_token(
        private_pem,
        sub="admin-1",
        username="admin",
        tenant_id=TENANT_A,
        roles=["groundwire-admin"],
    )
    _, run = await _seed_run_with_audit(auth_client, token, session_factory, actor="system")
    response = await auth_client.get(f"/v1/runs/{run['id']}/audit", headers=auth_headers(token))
    assert response.status_code == 200
    types = [row["event_type"] for row in response.json()]
    assert types == ["plan_completed", "run_completed"]


async def test_tenant_cannot_query_other_tenant_audit(auth_client, rsa_keys, session_factory):
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
    await _seed_run_with_audit(auth_client, token=admin_a, session_factory=session_factory)
    response = await auth_client.get("/v1/audit", headers=auth_headers(admin_b))
    assert response.status_code == 200
    assert response.json() == []


async def test_audit_date_range_filter(client, session_factory):
    agent = (await client.post("/v1/agents", json=AGENT_BODY)).json()
    run = (
        await client.post(
            "/v1/runs",
            json={"agent_id": agent["id"], "payload": {"to": "ops@example.com"}},
        )
    ).json()
    old = datetime(2020, 1, 1, tzinfo=timezone.utc)
    async with session_factory() as session:
        db_run = await get_run(session, UUID(run["id"]))
        assert db_run is not None
        session.add(
            AuditRecord(
                tenant_id=DEFAULT_TENANT_ID,
                run_id=db_run.id,
                event_type="plan_completed",
                actor="system",
                payload={},
                created_at=old,
            )
        )
        await session.commit()
    since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    recent = await client.get("/v1/audit", params={"since": since})
    assert recent.status_code == 200
    assert recent.json() == []
    until = datetime(2021, 1, 1, tzinfo=timezone.utc).isoformat()
    historic = await client.get("/v1/audit", params={"until": until})
    assert any(row["event_type"] == "plan_completed" for row in historic.json())
