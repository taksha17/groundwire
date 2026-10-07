from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from temporalio import activity

from groundwire.models import AuditRecord, Run
from groundwire.temporal.payloads import PlanResult, RunWorkflowInput, ToolCall

_session_factory: async_sessionmaker[AsyncSession] | None = None


def configure_activities(factory: async_sessionmaker[AsyncSession] | None) -> None:
    global _session_factory
    _session_factory = factory


@activity.defn
async def persist_run_progress(
    run_id: str,
    status: str,
    current_step: str | None,
    pending_action: dict | None,
) -> None:
    if _session_factory is None:
        return
    async with _session_factory() as session:
        run = await session.get(Run, UUID(run_id))
        if run is None:
            return
        run.status = status
        run.current_step = current_step
        run.pending_action = pending_action
        await session.commit()


@activity.defn
async def write_audit(
    run_id: str,
    tenant_id: str,
    event_type: str,
    actor: str,
    payload: dict,
) -> None:
    if _session_factory is None:
        return
    async with _session_factory() as session:
        session.add(
            AuditRecord(
                tenant_id=UUID(tenant_id),
                run_id=UUID(run_id),
                event_type=event_type,
                actor=actor,
                payload=payload,
            )
        )
        await session.commit()


@activity.defn
async def plan_run(input: RunWorkflowInput) -> PlanResult:
    payload = input.payload
    missing = [key for key in ("to", "subject", "body") if key not in payload]
    if missing:
        raise ValueError("payload must include to, subject, and body")
    return PlanResult(
        summary=f"Send email to {payload['to']}",
        tool_calls=[
            ToolCall(
                tool="send_email",
                params={
                    "to": payload["to"],
                    "subject": payload["subject"],
                    "body": payload["body"],
                },
                rationale="Notify the recipient using the planned email",
            )
        ],
    )


@activity.defn
async def execute_tool(tool: str, params: dict) -> dict:
    return {"tool": tool, "params": params, "result": "executed"}
