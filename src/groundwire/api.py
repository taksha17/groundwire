from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from groundwire.db import create_tables, make_engine, make_session_factory
from groundwire.schemas import (
    AgentCreate,
    AgentRead,
    ApprovalCreate,
    GraphEdgeRead,
    GraphNodeRead,
    RunCreate,
    RunGraphRead,
    RunRead,
)
from groundwire.services.agents import get_agent, list_agents, register_agent
from groundwire.services.graph import build_run_graph
from groundwire.services.approvals import (
    RunNotAwaitingApprovalError,
    RunNotFoundError,
    decide_approval,
)
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


app = FastAPI(title="Groundwire", version="0.2.0", lifespan=lifespan)
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


@app.post("/v1/agents", response_model=AgentRead, status_code=201)
async def create_agent(
    body: AgentCreate,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AgentRead:
    agent = await register_agent(
        session,
        name=body.name,
        allowed_tools=body.allowed_tools,
        approval_policy=body.approval_policy,
        tenant_id=settings.default_tenant_id,
    )
    return AgentRead.model_validate(agent)


@app.get("/v1/agents", response_model=list[AgentRead])
async def read_agents(session: AsyncSession = Depends(get_session)) -> list[AgentRead]:
    agents = await list_agents(session)
    return [AgentRead.model_validate(agent) for agent in agents]


@app.get("/v1/agents/{agent_id}", response_model=AgentRead)
async def read_agent(agent_id: UUID, session: AsyncSession = Depends(get_session)) -> AgentRead:
    agent = await get_agent(session, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return AgentRead.model_validate(agent)


@app.post("/v1/runs", response_model=RunRead, status_code=201)
async def create_run(
    body: RunCreate,
    session: AsyncSession = Depends(get_session),
    temporal: TemporalPort = Depends(get_temporal),
    settings: Settings = Depends(get_settings),
) -> RunRead:
    try:
        run = await start_run(
            session,
            temporal,
            agent_id=body.agent_id,
            payload=body.payload,
            tenant_id=settings.default_tenant_id,
        )
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail="agent not found") from None
    return to_run_read(run)


@app.get("/v1/runs", response_model=list[RunRead])
async def read_runs(
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[RunRead]:
    runs = await list_runs(session, status=status)
    return [to_run_read(run) for run in runs]


@app.get("/v1/runs/{run_id}/graph", response_model=RunGraphRead)
async def read_run_graph(run_id: UUID, session: AsyncSession = Depends(get_session)) -> RunGraphRead:
    run = await get_run(session, run_id)
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


@app.get("/v1/runs/{run_id}", response_model=RunRead)
async def read_run(run_id: UUID, session: AsyncSession = Depends(get_session)) -> RunRead:
    run = await get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return to_run_read(run)


@app.post("/v1/runs/{run_id}/approvals", response_model=RunRead)
async def create_approval(
    run_id: UUID,
    body: ApprovalCreate,
    session: AsyncSession = Depends(get_session),
    temporal: TemporalPort = Depends(get_temporal),
) -> RunRead:
    try:
        run = await decide_approval(
            session,
            temporal,
            run_id=run_id,
            decision=body.decision,
            edited_params=body.edited_params,
            actor=body.actor,
        )
    except RunNotFoundError:
        raise HTTPException(status_code=404, detail="run not found") from None
    except RunNotAwaitingApprovalError:
        raise HTTPException(status_code=409, detail="run is not awaiting approval") from None
    loaded = await get_run(session, run.id)
    return to_run_read(loaded or run)
