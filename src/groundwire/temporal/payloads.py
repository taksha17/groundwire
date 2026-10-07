from dataclasses import dataclass, field


@dataclass
class RunWorkflowInput:
    run_id: str
    tenant_id: str
    agent_id: str
    agent_name: str
    agent_version: int
    allowed_tools: list[str]
    approval_policy: dict
    payload: dict


@dataclass
class ApprovalDecision:
    decision: str
    edited_params: dict | None = None
    actor: str = "anonymous"


@dataclass
class ToolCall:
    tool: str
    params: dict
    rationale: str


@dataclass
class PlanResult:
    summary: str
    tool_calls: list[ToolCall] = field(default_factory=list)
