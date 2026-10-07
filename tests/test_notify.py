import httpx

from groundwire.temporal.activities import build_approval_ping, notify_approval


def test_build_approval_ping_points_at_the_box():
    ping = build_approval_ping(
        run_id="run-1",
        tenant_id="00000000-0000-0000-0000-000000000001",
        agent_name="langchain-ops-email",
        pending_action={"tool": "send_email", "params": {"to": "ops@example.com"}},
        dashboard_url="http://localhost:4200/",
    )
    assert ping["event"] == "approval_requested"
    assert ping["tool"] == "send_email"
    assert ping["dashboard_url"] == "http://localhost:4200"


async def test_notify_approval_skips_when_unconfigured(monkeypatch):
    monkeypatch.setattr(
        "groundwire.temporal.activities.get_settings",
        lambda: type("S", (), {"approval_webhook_url": "", "approval_webhook_secret": "", "dashboard_public_url": "http://localhost:4200"})(),
    )
    result = await notify_approval("run-1", "tenant", "ops", {"tool": "send_email"})
    assert result == {"sent": False, "reason": "unconfigured"}


async def test_notify_approval_posts_json(monkeypatch):
    seen: dict = {}

    class FakeResponse:
        status_code = 204

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json, headers):
            seen["url"] = url
            seen["json"] = json
            seen["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr(
        "groundwire.temporal.activities.get_settings",
        lambda: type(
            "S",
            (),
            {
                "approval_webhook_url": "http://sink.example/hook",
                "approval_webhook_secret": "s3cret",
                "dashboard_public_url": "http://localhost:4200",
            },
        )(),
    )
    monkeypatch.setattr("groundwire.temporal.activities.httpx.AsyncClient", FakeClient)
    result = await notify_approval(
        "run-1",
        "tenant",
        "ops",
        {"tool": "send_email", "params": {"to": "ops@example.com"}},
    )
    assert result == {"sent": True, "status_code": 204}
    assert seen["url"] == "http://sink.example/hook"
    assert seen["json"]["event"] == "approval_requested"
    assert seen["headers"]["Authorization"] == "Bearer s3cret"


async def test_notify_approval_does_not_raise_on_http_error(monkeypatch):
    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json, headers):
            raise httpx.ConnectError("down")

    monkeypatch.setattr(
        "groundwire.temporal.activities.get_settings",
        lambda: type(
            "S",
            (),
            {
                "approval_webhook_url": "http://sink.example/hook",
                "approval_webhook_secret": "",
                "dashboard_public_url": "http://localhost:4200",
            },
        )(),
    )
    monkeypatch.setattr("groundwire.temporal.activities.httpx.AsyncClient", FakeClient)
    result = await notify_approval("run-1", "tenant", "ops", {"tool": "send_email"})
    assert result["sent"] is False
    assert "down" in result["reason"]
