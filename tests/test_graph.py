from groundwire.services.graph import build_run_graph


def test_graph_while_awaiting_approval():
    nodes, edges = build_run_graph(
        status="awaiting_approval",
        pending_action={
            "tool": "send_email",
            "params": {"to": "ops@example.com"},
            "rationale": "Notify ops",
        },
        events=["run_started", "plan_completed", "approval_requested"],
    )
    by_id = {node.id: node for node in nodes}
    assert [node.id for node in nodes] == ["plan", "approval", "send_email"]
    assert by_id["plan"].status == "completed"
    assert by_id["approval"].status == "awaiting_approval"
    assert by_id["approval"].detail == {
        "tool": "send_email",
        "params": {"to": "ops@example.com"},
        "rationale": "Notify ops",
    }
    assert by_id["send_email"].status == "pending"
    assert [(edge.source, edge.target) for edge in edges] == [
        ("plan", "approval"),
        ("approval", "send_email"),
    ]


def test_graph_after_reject_skips_tool():
    nodes, _ = build_run_graph(
        status="rejected",
        pending_action={"tool": "send_email", "params": {}, "rationale": "x"},
        events=["run_started", "plan_completed", "approval_requested", "approval_rejected"],
    )
    by_id = {node.id: node for node in nodes}
    assert by_id["approval"].status == "rejected"
    assert by_id["send_email"].status == "skipped"


def test_graph_includes_router_when_routed():
    nodes, edges = build_run_graph(
        status="awaiting_approval",
        pending_action={
            "tool": "send_email",
            "params": {},
            "rationale": "x",
            "model": "groundwire-small",
            "estimated_cost_usd": 0.0001,
        },
        events=["run_started", "plan_completed", "model_routed", "approval_requested"],
    )
    assert [node.id for node in nodes] == ["plan", "route", "approval", "send_email"]
    assert nodes[1].name == "groundwire-small"
    assert [(edge.source, edge.target) for edge in edges] == [
        ("plan", "route"),
        ("route", "approval"),
        ("approval", "send_email"),
    ]


def test_graph_completed_executes_tool():
    nodes, _ = build_run_graph(
        status="completed",
        pending_action=None,
        events=[
            "run_started",
            "plan_completed",
            "approval_requested",
            "approval_granted",
            "tool_executed",
            "run_completed",
        ],
        tool="send_email",
    )
    by_id = {node.id: node for node in nodes}
    assert by_id["plan"].status == "completed"
    assert by_id["approval"].status == "completed"
    assert by_id["send_email"].status == "completed"
