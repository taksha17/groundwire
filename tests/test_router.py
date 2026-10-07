from groundwire.temporal.activities import fallback_route, route_model
from groundwire.temporal.payloads import RouteDecision


def test_fallback_keeps_short_email_on_small_model():
    decision = fallback_route("send_email", "Notify the recipient using the planned email")
    assert decision.model == "groundwire-small"
    assert decision.estimated_cost_usd > 0
    assert decision.routed is False


def test_fallback_sends_reasoning_to_large_model():
    decision = fallback_route(
        "write_brief",
        "Analyze the incident and reason about which on-call rotation should be paged.",
    )
    assert decision.model == "groundwire-large"


async def test_route_model_uses_python_fallback_without_router_url(monkeypatch):
    monkeypatch.setattr("groundwire.temporal.activities.get_settings", lambda: type("S", (), {"router_url": ""})())
    decision = await route_model("send_email", "hi")
    assert isinstance(decision, RouteDecision)
    assert decision.model == "groundwire-small"
