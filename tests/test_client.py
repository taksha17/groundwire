import json

import httpx

from groundwire.client import GroundwireClient, GroundwireError
from groundwire.handoff import canned_outage_email, ensure_ops_agent, start_gated_email


class FakePlane:
    def __init__(self) -> None:
        self.agents: list[dict] = []
        self.runs: list[dict] = []
        self.auth: str | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.auth = request.headers.get("authorization")
        path = request.url.path
        if request.method == "POST" and path == "/v1/agents":
            body = json.loads(request.content)
            agent = {
                "id": f"agent-{len(self.agents) + 1}",
                "name": body["name"],
                "allowed_tools": body["allowed_tools"],
                "approval_policy": body["approval_policy"],
            }
            self.agents.append(agent)
            return httpx.Response(201, json=agent)
        if request.method == "GET" and path == "/v1/agents":
            return httpx.Response(200, json=self.agents)
        if request.method == "POST" and path == "/v1/runs":
            body = json.loads(request.content)
            run = {
                "id": f"run-{len(self.runs) + 1}",
                "agent_id": body["agent_id"],
                "agent_name": next(a["name"] for a in self.agents if a["id"] == body["agent_id"]),
                "status": "planning",
                "payload": body["payload"],
            }
            self.runs.append(run)
            return httpx.Response(201, json=run)
        if request.method == "GET" and path.startswith("/v1/runs/"):
            run_id = path.rsplit("/", 1)[-1]
            for run in self.runs:
                if run["id"] == run_id:
                    return httpx.Response(200, json=run)
            return httpx.Response(404, json={"detail": "run not found"})
        if request.method == "GET" and path == "/v1/me":
            return httpx.Response(200, json={"subject": "admin"})
        return httpx.Response(404, json={"detail": "missing"})


def _gw(plane: FakePlane, token: str | None = None) -> GroundwireClient:
    http = httpx.Client(transport=httpx.MockTransport(plane), base_url="http://test")
    return GroundwireClient("http://test", token=token, client=http)


def test_client_registers_agent_and_starts_run():
    plane = FakePlane()
    gw = _gw(plane)
    agent = gw.register_agent("demo-ops-agent", ["send_email"], {"require_approval_for": ["send_email"]})
    payload = canned_outage_email("edge cache miss")
    run = gw.start_run(agent["id"], payload)
    assert run["status"] == "planning"
    assert plane.runs[0]["payload"] == payload
    assert "edge cache miss" in payload["subject"]
    assert gw.list_agents()[0]["id"] == agent["id"]
    assert gw.get_run(run["id"])["id"] == run["id"]


def test_handoff_reuses_named_agent():
    plane = FakePlane()
    gw = _gw(plane)
    first = ensure_ops_agent(gw, "langchain-ops-email")
    second = ensure_ops_agent(gw, "langchain-ops-email")
    assert first["id"] == second["id"]
    assert len(plane.agents) == 1
    run = start_gated_email(gw, first["id"], canned_outage_email("db failover"))
    assert run["agent_name"] == "langchain-ops-email"


def test_start_gated_email_requires_fields():
    plane = FakePlane()
    gw = _gw(plane)
    agent = ensure_ops_agent(gw, "crew-ops-email")
    try:
        start_gated_email(gw, agent["id"], {"to": "ops@example.com"})
    except ValueError as exc:
        assert "subject" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_client_surfaces_http_errors():
    gw = _gw(FakePlane())
    try:
        gw.get_run("missing")
    except GroundwireError as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("expected GroundwireError")


def test_login_password_stores_token_without_returning_it(monkeypatch):
    class FakeResponse:
        status_code = 200

        def json(self):
            return {"access_token": "secret-token"}

    monkeypatch.setattr("groundwire.client.httpx.post", lambda *args, **kwargs: FakeResponse())
    plane = FakePlane()
    gw = _gw(plane)
    assert gw.login_password("http://idp/token", "admin", "admin") is None
    assert gw.me()["subject"] == "admin"
    assert plane.auth == "Bearer secret-token"
