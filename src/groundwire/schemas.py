from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ApprovalPolicy(BaseModel):
    require_approval_for: list[str] = Field(default_factory=list)


class AgentCreate(BaseModel):
    name: str = Field(min_length=1)
    allowed_tools: list[str] = Field(min_length=1)
    approval_policy: ApprovalPolicy


class AgentRead(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    allowed_tools: list[str]
    approval_policy: ApprovalPolicy
    version: int

    model_config = {"from_attributes": True}


class RunCreate(BaseModel):
    agent_id: UUID
    payload: dict


class RunRead(BaseModel):
    id: UUID
    agent_definition_id: UUID
    agent_version: int
    temporal_workflow_id: str
    status: str
    payload: dict
    pending_action: dict | None = None
    current_step: str | None = None
    created_at: datetime | None = None
    agent_name: str | None = None

    model_config = {"from_attributes": True}


class GraphNodeRead(BaseModel):
    id: str
    type: str
    name: str
    status: str
    detail: dict | None = None


class GraphEdgeRead(BaseModel):
    source: str
    target: str


class RunGraphRead(BaseModel):
    nodes: list[GraphNodeRead]
    edges: list[GraphEdgeRead]


class ApprovalCreate(BaseModel):
    decision: str = Field(pattern="^(approve|reject|edit)$")
    edited_params: dict | None = None
    actor: str = "anonymous"


class MetricsRead(BaseModel):
    runs: int
    completed: int
    rejected: int
    failed: int
    success_rate: float
    avg_duration_seconds: float
    avg_approval_seconds: float
    cost_per_run: float


class IdentityRead(BaseModel):
    subject: str
    username: str
    tenant_id: UUID
    roles: list[str]


class AuditRecordRead(BaseModel):
    id: UUID
    tenant_id: UUID
    run_id: UUID
    agent_id: UUID | None = None
    event_type: str
    actor: str
    payload: dict
    created_at: datetime | None = None
    outcome: str | None = None
