from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from groundwire.enums import RunStatus
from groundwire.models import Run
from groundwire.services.runs import get_run
from groundwire.temporal.payloads import ApprovalDecision
from groundwire.temporal.port import TemporalPort


class RunNotFoundError(Exception):
    pass


class RunNotAwaitingApprovalError(Exception):
    pass


async def decide_approval(
    session: AsyncSession,
    temporal: TemporalPort,
    *,
    run_id: UUID,
    decision: str,
    edited_params: dict | None = None,
    actor: str = "anonymous",
) -> Run:
    run = await get_run(session, run_id)
    if run is None:
        raise RunNotFoundError(str(run_id))
    if run.status != RunStatus.AWAITING_APPROVAL:
        raise RunNotAwaitingApprovalError(run.status)
    await temporal.signal_approval(
        run_id,
        ApprovalDecision(decision=decision, edited_params=edited_params, actor=actor),
    )
    return run
