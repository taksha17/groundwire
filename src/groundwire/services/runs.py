from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from groundwire.enums import RunStatus
from groundwire.models import AuditRecord, Run
from groundwire.services.agents import get_agent
from groundwire.settings import DEFAULT_TENANT_ID
from groundwire.temporal.payloads import RunWorkflowInput
from groundwire.temporal.port import TemporalPort


class AgentNotFoundError(Exception):
    pass


async def start_run(
    session: AsyncSession,
    temporal: TemporalPort,
    *,
    agent_id: UUID,
    payload: dict,
    tenant_id: UUID | None = None,
) -> Run:
    agent = await get_agent(session, agent_id)
    if agent is None:
        raise AgentNotFoundError(str(agent_id))

    run_id = uuid4()
    resolved_tenant = tenant_id or DEFAULT_TENANT_ID
    run = Run(
        id=run_id,
        tenant_id=resolved_tenant,
        agent_definition_id=agent.id,
        agent_version=agent.version,
        temporal_workflow_id=f"run-{run_id}",
        status=RunStatus.PLANNING,
        payload=payload,
    )
    session.add(run)
    await session.commit()
    loaded = await get_run(session, run_id)
    assert loaded is not None

    await temporal.start_run_workflow(
        RunWorkflowInput(
            run_id=str(run.id),
            tenant_id=str(run.tenant_id),
            agent_id=str(agent.id),
            agent_name=agent.name,
            agent_version=agent.version,
            allowed_tools=list(agent.allowed_tools),
            approval_policy=dict(agent.approval_policy),
            payload=payload,
        )
    )
    return loaded


def to_run_read(run: Run) -> "RunRead":
    from groundwire.schemas import RunRead

    return RunRead(
        id=run.id,
        agent_definition_id=run.agent_definition_id,
        agent_version=run.agent_version,
        temporal_workflow_id=run.temporal_workflow_id,
        status=run.status,
        payload=run.payload,
        pending_action=run.pending_action,
        current_step=run.current_step,
        created_at=run.created_at,
        agent_name=run.agent_definition.name if run.agent_definition else None,
    )


async def get_run(session: AsyncSession, run_id: UUID) -> Run | None:
    result = await session.execute(
        select(Run).options(selectinload(Run.agent_definition)).where(Run.id == run_id)
    )
    return result.scalar_one_or_none()


async def list_runs(session: AsyncSession, *, status: str | None = None) -> list[Run]:
    stmt = select(Run).options(selectinload(Run.agent_definition)).order_by(Run.created_at.desc())
    if status is not None:
        stmt = stmt.where(Run.status == status)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_audit_events(session: AsyncSession, run_id: UUID) -> list[str]:
    result = await session.execute(
        select(AuditRecord.event_type)
        .where(AuditRecord.run_id == run_id)
        .order_by(AuditRecord.created_at.asc())
    )
    return list(result.scalars().all())
