from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from groundwire.auth import get_identity
from groundwire.db import create_tables, make_engine, make_session_factory
from groundwire.identity import Identity
from groundwire.schemas import (
    AgentCreate,
    AgentRead,
    ApprovalCreate,
    AuditRecordRead,
    GraphEdgeRead,
    GraphNodeRead,
    IdentityRead,
    MetricsRead,
    RunCreate,
    RunGraphRead,
    RunRead,
)
from groundwire.services.agents import get_agent, list_agents, register_agent
from groundwire.services.audit import audit_csv, query_audit
from groundwire.services.metrics import compute_metrics
from groundwire.services.graph import build_run_graph
from groundwire.services.approvals import (
    RunNotAwaitingApprovalError,
    RunNotFoundError,
    decide_approval,
)
from groundwire.services.policies import PolicyDeniedError, assert_can_approve, assert_can_register
from groundwire.services.runs import (
    AgentNotFoundError,
    get_run,
    list_audit_events,
    list_runs,
    start_run,
    to_run_read,
)
from groundwire.settings import Settings, get_settings
from groundwire.temporal.client import connect_temporal
from groundwire.temporal.port import TemporalPort

_session_factory: async_sessionmaker[AsyncSession] | None = None
_temporal: TemporalPort | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _session_factory, _temporal
    settings = get_settings()
    engine = make_engine(settings.database_url)
    _session_factory = make_session_factory(engine)
    await create_tables(engine)
    _temporal = await connect_temporal(settings)
    app.state.engine = engine
    yield
    await engine.dispose()
    _session_factory = None
    _temporal = None


app = FastAPI(title="Groundwire", version="0.4.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://127.0.0.1:4200", "*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_session() -> AsyncIterator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("database session factory is not initialized")
    async with _session_factory() as session:
        yield session


def get_temporal() -> TemporalPort:
    if _temporal is None:
        raise RuntimeError("temporal client is not initialized")
    return _temporal


def _to_audit_read(record, run) -> AuditRecordRead:
    return AuditRecordRead(
        id=record.id,
        tenant_id=record.tenant_id,
        run_id=record.run_id,
        agent_id=run.agent_definition_id,
        event_type=record.event_type,
        actor=record.actor,
        payload=record.payload,
        created_at=record.created_at,
        outcome=run.status,
    )


@app.get("/v1/me", response_model=IdentityRead)
async def read_me(identity: Identity = Depends(get_identity)) -> IdentityRead:
    return IdentityRead(
        subject=identity.subject,
        username=identity.username,
        tenant_id=identity.tenant_id,
        roles=sorted(identity.roles),
    )


@app.post("/v1/agents", response_model=AgentRead, status_code=201)
async def create_agent(
    body: AgentCreate,
    session: AsyncSession = Depends(get_session),
    identity: Identity = Depends(get_identity),
) -> AgentRead:
    try:
        await assert_can_register(session, identity)
    except PolicyDeniedError:
        raise HTTPException(status_code=403, detail="not allowed to register agents") from None
    agent = await register_agent(
        session,
        name=body.name,
        allowed_tools=body.allowed_tools,
        approval_policy=body.approval_policy,
        tenant_id=identity.tenant_id,
    )
    return AgentRead.model_validate(agent)


@app.get("/v1/agents", response_model=list[AgentRead])
async def read_agents(
    session: AsyncSession = Depends(get_session),
    identity: Identity = Depends(get_identity),
) -> list[AgentRead]:
    agents = await list_agents(session, tenant_id=identity.tenant_id)
    return [AgentRead.model_validate(agent) for agent in agents]


@app.get("/v1/agents/{agent_id}", response_model=AgentRead)
async def read_agent(
    agent_id: UUID,
    session: AsyncSession = Depends(get_session),
    identity: Identity = Depends(get_identity),
) -> AgentRead:
    agent = await get_agent(session, agent_id, tenant_id=identity.tenant_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return AgentRead.model_validate(agent)


@app.post("/v1/runs", response_model=RunRead, status_code=201)
async def create_run(
    body: RunCreate,
    session: AsyncSession = Depends(get_session),
    temporal: TemporalPort = Depends(get_temporal),
    identity: Identity = Depends(get_identity),
) -> RunRead:
    try:
        run = await start_run(
            session,
            temporal,
            agent_id=body.agent_id,
            payload=body.payload,
            tenant_id=identity.tenant_id,
        )
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail="agent not found") from None
    return to_run_read(run)


@app.get("/v1/runs", response_model=list[RunRead])
async def read_runs(
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    identity: Identity = Depends(get_identity),
) -> list[RunRead]:
    runs = await list_runs(session, tenant_id=identity.tenant_id, status=status)
    return [to_run_read(run) for run in runs]


@app.get("/v1/runs/{run_id}/graph", response_model=RunGraphRead)
async def read_run_graph(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    identity: Identity = Depends(get_identity),
) -> RunGraphRead:
    run = await get_run(session, run_id, tenant_id=identity.tenant_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    events = await list_audit_events(session, run_id)
    nodes, edges = build_run_graph(
        status=run.status,
        pending_action=run.pending_action,
        events=events,
    )
    return RunGraphRead(
        nodes=[GraphNodeRead.model_validate(node, from_attributes=True) for node in nodes],
        edges=[GraphEdgeRead.model_validate(edge, from_attributes=True) for edge in edges],
    )


@app.get("/v1/runs/{run_id}/audit", response_model=list[AuditRecordRead])
async def read_run_audit(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    identity: Identity = Depends(get_identity),
) -> list[AuditRecordRead]:
    run = await get_run(session, run_id, tenant_id=identity.tenant_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    rows = await query_audit(session, tenant_id=identity.tenant_id, run_id=run_id)
    return [_to_audit_read(record, linked) for record, linked in rows]


@app.get("/v1/runs/{run_id}", response_model=RunRead)
async def read_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
    identity: Identity = Depends(get_identity),
) -> RunRead:
    run = await get_run(session, run_id, tenant_id=identity.tenant_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return to_run_read(run)


@app.post("/v1/runs/{run_id}/approvals", response_model=RunRead)
async def create_approval(
    run_id: UUID,
    body: ApprovalCreate,
    session: AsyncSession = Depends(get_session),
    temporal: TemporalPort = Depends(get_temporal),
    identity: Identity = Depends(get_identity),
    settings: Settings = Depends(get_settings),
) -> RunRead:
    run = await get_run(session, run_id, tenant_id=identity.tenant_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    tool = None
    if isinstance(run.pending_action, dict):
        tool = run.pending_action.get("tool")
    try:
        await assert_can_approve(session, identity, tool)
    except PolicyDeniedError:
        raise HTTPException(status_code=403, detail="not allowed to approve this tool") from None
    actor = identity.username if settings.auth_enabled else body.actor
    try:
        run = await decide_approval(
            session,
            temporal,
            run_id=run_id,
            decision=body.decision,
            edited_params=body.edited_params,
            actor=actor,
            tenant_id=identity.tenant_id,
        )
    except RunNotFoundError:
        raise HTTPException(status_code=404, detail="run not found") from None
    except RunNotAwaitingApprovalError:
        raise HTTPException(status_code=409, detail="run is not awaiting approval") from None
    loaded = await get_run(session, run.id, tenant_id=identity.tenant_id)
    return to_run_read(loaded or run)


@app.get("/v1/metrics", response_model=MetricsRead)
async def read_metrics(
    session: AsyncSession = Depends(get_session),
    identity: Identity = Depends(get_identity),
) -> MetricsRead:
    return MetricsRead.model_validate(await compute_metrics(session, tenant_id=identity.tenant_id))


@app.get("/v1/audit")
async def read_audit(
    agent_id: UUID | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    event_type: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    format: str = Query(default="json", pattern="^(json|csv)$"),
    session: AsyncSession = Depends(get_session),
    identity: Identity = Depends(get_identity),
):
    rows = await query_audit(
        session,
        tenant_id=identity.tenant_id,
        agent_id=agent_id,
        since=since,
        until=until,
        event_type=event_type,
        outcome=outcome,
    )
    if format == "csv":
        return Response(
            content=audit_csv(rows),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=groundwire-audit.csv"},
        )
    return [_to_audit_read(record, run) for record, run in rows]
