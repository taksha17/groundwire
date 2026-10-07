import csv
import io
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from groundwire.models import AuditRecord, Run


async def query_audit(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    event_type: str | None = None,
    outcome: str | None = None,
    run_id: UUID | None = None,
) -> list[tuple[AuditRecord, Run]]:
    stmt = (
        select(AuditRecord, Run)
        .join(Run, AuditRecord.run_id == Run.id)
        .where(AuditRecord.tenant_id == tenant_id)
        .order_by(AuditRecord.created_at.asc())
    )
    if run_id is not None:
        stmt = stmt.where(AuditRecord.run_id == run_id)
    if agent_id is not None:
        stmt = stmt.where(Run.agent_definition_id == agent_id)
    if since is not None:
        stmt = stmt.where(AuditRecord.created_at >= since)
    if until is not None:
        stmt = stmt.where(AuditRecord.created_at <= until)
    if event_type is not None:
        stmt = stmt.where(AuditRecord.event_type == event_type)
    if outcome is not None:
        stmt = stmt.where(Run.status == outcome)
    result = await session.execute(stmt)
    return list(result.all())


def audit_csv(rows: list[tuple[AuditRecord, Run]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "created_at",
            "tenant_id",
            "run_id",
            "agent_id",
            "event_type",
            "actor",
            "outcome",
            "payload",
        ]
    )
    for record, run in rows:
        writer.writerow(
            [
                str(record.id),
                record.created_at.isoformat() if record.created_at else "",
                str(record.tenant_id),
                str(record.run_id),
                str(run.agent_definition_id),
                record.event_type,
                record.actor,
                run.status,
                json.dumps(record.payload),
            ]
        )
    return buffer.getvalue()
