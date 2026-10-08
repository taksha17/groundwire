import httpx
import pytest

from groundwire.services.runs import with_approval_timeout
from groundwire.temporal.activities import execute_tool


def test_with_approval_timeout_injects_seconds():
    policy = with_approval_timeout({"require_approval_for": ["send_email"]}, 72)
    assert policy["timeout_seconds"] == 72 * 3600
    assert policy["require_approval_for"] == ["send_email"]


def test_with_approval_timeout_keeps_explicit_seconds():
    policy = with_approval_timeout({"timeout_seconds": 30}, 72)
    assert policy["timeout_seconds"] == 30


def test_with_approval_timeout_zero_hours_leaves_policy():
    policy = with_approval_timeout({"require_approval_for": ["send_email"]}, 0)
    assert "timeout_seconds" not in policy


async def test_execute_tool_records_without_delivery_when_unconfigured(monkeypatch):
    monkeypatch.setattr(
        "groundwire.temporal.activities.get_settings",
        lambda: type("S", (), {"tool_executor_url": "", "tool_executor_secret": ""})(),
    )
    result = await execute_tool("send_email", {"to": "a@b.c", "subject": "Hi", "body": "x"})
    assert result["result"] == "executed"
    assert result["delivered"] is False


async def test_execute_tool_posts_approved_params(monkeypatch):
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
            {"tool_executor_url": "http://mailer.example/send", "tool_executor_secret": "s3cret"},
        )(),
    )
    monkeypatch.setattr("groundwire.temporal.activities.httpx.AsyncClient", FakeClient)
    params = {"to": "hiring@co.example", "subject": "Referral", "body": "Please consider."}
    result = await execute_tool("send_email", params)
    assert result["delivered"] is True
    assert result["status_code"] == 204
    assert seen["url"] == "http://mailer.example/send"
    assert seen["json"] == {"event": "execute_tool", "tool": "send_email", "params": params}
    assert seen["headers"]["Authorization"] == "Bearer s3cret"


async def test_execute_tool_raises_when_mailer_rejects(monkeypatch):
    class FakeResponse:
        status_code = 500
        text = "no"

        def raise_for_status(self) -> None:
            raise httpx.HTTPStatusError("no", request=None, response=None)

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json, headers):
            return FakeResponse()

    monkeypatch.setattr(
        "groundwire.temporal.activities.get_settings",
        lambda: type("S", (), {"tool_executor_url": "http://mailer.example/send", "tool_executor_secret": ""})(),
    )
    monkeypatch.setattr("groundwire.temporal.activities.httpx.AsyncClient", FakeClient)
    with pytest.raises(httpx.HTTPError):
        await execute_tool("send_email", {"to": "a@b.c"})
