async def test_register_agent_returns_version_1(client):
    response = await client.post(
        "/v1/agents",
        json={
            "name": "demo-ops-agent",
            "allowed_tools": ["send_email"],
            "approval_policy": {"require_approval_for": ["send_email"]},
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "demo-ops-agent"
    assert body["version"] == 1
    assert body["allowed_tools"] == ["send_email"]
    assert body["approval_policy"]["require_approval_for"] == ["send_email"]


async def test_get_agent_round_trip(client):
    created = (
        await client.post(
            "/v1/agents",
            json={
                "name": "demo-ops-agent",
                "allowed_tools": ["send_email"],
                "approval_policy": {"require_approval_for": ["send_email"]},
            },
        )
    ).json()
    response = await client.get(f"/v1/agents/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_get_unknown_agent_404(client):
    response = await client.get("/v1/agents/00000000-0000-0000-0000-000000000099")
    assert response.status_code == 404


async def test_register_agent_rejects_empty_name(client):
    response = await client.post(
        "/v1/agents",
        json={
            "name": "",
            "allowed_tools": ["send_email"],
            "approval_policy": {"require_approval_for": []},
        },
    )
    assert response.status_code == 422


async def test_register_agent_rejects_empty_allowed_tools(client):
    response = await client.post(
        "/v1/agents",
        json={
            "name": "demo-ops-agent",
            "allowed_tools": [],
            "approval_policy": {"require_approval_for": []},
        },
    )
    assert response.status_code == 422
