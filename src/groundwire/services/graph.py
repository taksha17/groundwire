from dataclasses import dataclass


@dataclass
class GraphNode:
    id: str
    type: str
    name: str
    status: str
    detail: dict | None = None


@dataclass
class GraphEdge:
    source: str
    target: str


def build_run_graph(
    *,
    status: str,
    pending_action: dict | None,
    events: list[str],
    tool: str | None = None,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    tool_name = tool
    if tool_name is None and pending_action and pending_action.get("tool"):
        tool_name = str(pending_action["tool"])
    if tool_name is None:
        tool_name = "send_email"

    plan_status = "pending"
    approval_status = "pending"
    tool_status = "pending"

    if "run_started" in events or "plan_completed" in events or status != "planning":
        plan_status = "running"
    if "plan_completed" in events or status in {
        "awaiting_approval",
        "executing",
        "completed",
        "rejected",
        "failed",
    }:
        plan_status = "completed"

    if "approval_requested" in events or status == "awaiting_approval":
        approval_status = "awaiting_approval"
    if "approval_granted" in events or status in {"executing", "completed"}:
        approval_status = "completed"
    if "approval_rejected" in events or status == "rejected":
        approval_status = "rejected"
        tool_status = "skipped"

    if status == "executing":
        tool_status = "running"
    if "tool_executed" in events or status == "completed":
        tool_status = "completed"
    if status == "rejected":
        tool_status = "skipped"

    approval_detail = pending_action if approval_status == "awaiting_approval" else None

    nodes = [
        GraphNode(id="plan", type="planning", name="Plan", status=plan_status),
        GraphNode(
            id="approval",
            type="approval_gate",
            name="Approval",
            status=approval_status,
            detail=approval_detail,
        ),
        GraphNode(id=tool_name, type="tool_call", name=tool_name, status=tool_status),
    ]
    edges = [
        GraphEdge(source="plan", target="approval"),
        GraphEdge(source="approval", target=tool_name),
    ]
    return nodes, edges
