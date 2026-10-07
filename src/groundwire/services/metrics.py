from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from groundwire.enums import RunStatus
from groundwire.models import AuditRecord, Run

_TERMINAL = {RunStatus.COMPLETED, RunStatus.REJECTED, RunStatus.FAILED}


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


async def compute_metrics(session: AsyncSession, *, tenant_id: UUID) -> dict:
    runs = list(
        (
            await session.execute(select(Run).where(Run.tenant_id == tenant_id))
        ).scalars().all()
    )
    completed = sum(1 for run in runs if run.status == RunStatus.COMPLETED)
    rejected = sum(1 for run in runs if run.status == RunStatus.REJECTED)
    failed = sum(1 for run in runs if run.status == RunStatus.FAILED)
    terminal = completed + rejected + failed
    durations: list[float] = []
    for run in runs:
        if run.status not in _TERMINAL:
            continue
        start = _aware(run.created_at)
        end = _aware(run.updated_at)
        if start and end and end >= start:
            durations.append((end - start).total_seconds())

    events = list(
        (
            await session.execute(
                select(AuditRecord)
                .where(AuditRecord.tenant_id == tenant_id)
                .order_by(AuditRecord.created_at.asc())
            )
        ).scalars().all()
    )
    requested: dict[UUID, datetime] = {}
    holds: list[float] = []
    costs: list[float] = []
    for event in events:
        stamp = _aware(event.created_at)
        if stamp is None:
            continue
        if event.event_type == "approval_requested":
            requested[event.run_id] = stamp
        elif event.event_type in {"approval_granted", "approval_rejected"}:
            start = requested.pop(event.run_id, None)
            if start is not None and stamp >= start:
                holds.append((stamp - start).total_seconds())
        elif event.event_type == "model_routed":
            try:
                costs.append(float((event.payload or {}).get("estimated_cost_usd") or 0))
            except (TypeError, ValueError):
                pass

    return {
        "runs": len(runs),
        "completed": completed,
        "rejected": rejected,
        "failed": failed,
        "success_rate": (completed / terminal) if terminal else 0.0,
        "avg_duration_seconds": (sum(durations) / len(durations)) if durations else 0.0,
        "avg_approval_seconds": (sum(holds) / len(holds)) if holds else 0.0,
        "cost_per_run": (sum(costs) / len(runs)) if runs else 0.0,
    }
