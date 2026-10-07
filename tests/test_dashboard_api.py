async def test_list_agents(client):
    created = await client.post(
        "/v1/agents",
        json={
            "name": "demo-ops-agent",
            "allowed_tools": ["send_email"],
            "approval_policy": {"require_approval_for": ["send_email"]},
        },
    )
    response = await client.get("/v1/agents")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert created.json()["id"] in ids


async def test_run_includes_agent_name_and_timestamps(client):
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
                "payload": {"to": "ops@example.com", "subject": "Outage", "body": "x"},
            },
        )
    ).json()
    assert run["agent_name"] == "demo-ops-agent"
    assert run["created_at"]
    detail = await client.get(f"/v1/runs/{run['id']}")
    assert detail.json()["agent_name"] == "demo-ops-agent"


async def test_run_graph_endpoint(client, session_factory):
    from uuid import UUID

    from groundwire.enums import RunStatus
    from groundwire.models import AuditRecord
    from groundwire.services.runs import get_run
    from groundwire.settings import DEFAULT_TENANT_ID

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
                "payload": {"to": "ops@example.com", "subject": "Outage", "body": "x"},
            },
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
        session.add(
            AuditRecord(
                tenant_id=DEFAULT_TENANT_ID,
                run_id=db_run.id,
                event_type="plan_completed",
                actor="system",
                payload={},
            )
        )
        session.add(
            AuditRecord(
                tenant_id=DEFAULT_TENANT_ID,
                run_id=db_run.id,
                event_type="approval_requested",
                actor="system",
                payload=db_run.pending_action,
            )
        )
        await session.commit()

    response = await client.get(f"/v1/runs/{run['id']}/graph")
    assert response.status_code == 200
    body = response.json()
    assert [node["id"] for node in body["nodes"]] == ["plan", "approval", "send_email"]
    assert body["nodes"][1]["status"] == "awaiting_approval"


async def test_cors_preflight_allows_dashboard(client):
    response = await client.options(
        "/v1/runs",
        headers={
            "Origin": "http://localhost:4200",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") in {"*", "http://localhost:4200"}
