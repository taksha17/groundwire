from datetime import datetime, timedelta, timezone
from uuid import UUID

from groundwire.enums import RunStatus
from groundwire.models import AuditRecord
from groundwire.services.runs import get_run
from groundwire.settings import DEFAULT_TENANT_ID
from tests.conftest import AGENT_BODY


async def test_metrics_success_rate_and_duration(client, session_factory):
    agent = (await client.post("/v1/agents", json=AGENT_BODY)).json()
    run = (
        await client.post(
            "/v1/runs",
            json={"agent_id": agent["id"], "payload": {"to": "ops@example.com"}},
        )
    ).json()
    started = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    ended = started + timedelta(seconds=40)
    async with session_factory() as session:
        db_run = await get_run(session, UUID(run["id"]))
        assert db_run is not None
        db_run.status = RunStatus.COMPLETED
        db_run.created_at = started
        db_run.updated_at = ended
        session.add(
            AuditRecord(
                tenant_id=DEFAULT_TENANT_ID,
                run_id=db_run.id,
                event_type="approval_requested",
                actor="system",
                payload={},
                created_at=started + timedelta(seconds=5),
            )
        )
        session.add(
            AuditRecord(
                tenant_id=DEFAULT_TENANT_ID,
                run_id=db_run.id,
                event_type="approval_granted",
                actor="admin",
                payload={},
                created_at=started + timedelta(seconds=20),
            )
        )
        session.add(
            AuditRecord(
                tenant_id=DEFAULT_TENANT_ID,
                run_id=db_run.id,
                event_type="model_routed",
                actor="router",
                payload={"model": "groundwire-small", "estimated_cost_usd": 0.0004},
                created_at=started + timedelta(seconds=4),
            )
        )
        await session.commit()

    response = await client.get("/v1/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["runs"] == 1
    assert body["completed"] == 1
    assert body["success_rate"] == 1.0
    assert body["avg_duration_seconds"] == 40.0
    assert body["avg_approval_seconds"] == 15.0
    assert body["cost_per_run"] == 0.0004
