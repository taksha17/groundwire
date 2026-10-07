async def test_start_run_records_agent_version_and_workflow_id(client, fake_temporal):
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
    payload = {"to": "ops@example.com", "subject": "Outage", "body": "Please page on-call."}
    response = await client.post("/v1/runs", json={"agent_id": agent["id"], "payload": payload})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "planning"
    assert body["agent_version"] == 1
    assert body["temporal_workflow_id"] == f"run-{body['id']}"
    assert fake_temporal.started[0].payload == payload
    assert fake_temporal.started[0].agent_version == 1


async def test_get_run_round_trip(client):
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
    created = (
        await client.post(
            "/v1/runs",
            json={
                "agent_id": agent["id"],
                "payload": {"to": "ops@example.com", "subject": "Outage", "body": "x"},
            },
        )
    ).json()
    response = await client.get(f"/v1/runs/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_start_run_unknown_agent_404(client, fake_temporal):
    response = await client.post(
        "/v1/runs",
        json={
            "agent_id": "00000000-0000-0000-0000-000000000099",
            "payload": {"to": "ops@example.com"},
        },
    )
    assert response.status_code == 404
    assert fake_temporal.started == []
