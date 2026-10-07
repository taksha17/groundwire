import asyncio
from datetime import timedelta
from uuid import uuid4

from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from groundwire.temporal.payloads import ApprovalDecision, PlanResult, RunWorkflowInput, ToolCall
from groundwire.temporal.workflows import AgentRunWorkflow

TASK_QUEUE = "crash-agent-runs"


def _input() -> RunWorkflowInput:
    return RunWorkflowInput(
        run_id=str(uuid4()),
        tenant_id="00000000-0000-0000-0000-000000000001",
        agent_id=str(uuid4()),
        agent_name="demo-ops-agent",
        agent_version=1,
        allowed_tools=["send_email"],
        approval_policy={"require_approval_for": ["send_email"]},
        payload={"to": "ops@example.com", "subject": "Outage", "body": "Please page on-call."},
    )


@activity.defn(name="persist_run_progress")
async def persist_stub(run_id: str, status: str, current_step: str | None, pending_action: dict | None) -> None:
    return None


@activity.defn(name="write_audit")
async def audit_stub(run_id: str, tenant_id: str, event_type: str, actor: str, payload: dict) -> None:
    return None


@activity.defn(name="plan_run")
async def plan_stub(input: RunWorkflowInput) -> PlanResult:
    return PlanResult(
        summary="Send an operational email",
        tool_calls=[
            ToolCall(tool="send_email", params=input.payload, rationale="Notify ops of the outage")
        ],
    )


@activity.defn(name="route_model")
async def route_stub(task: str, prompt: str):
    from groundwire.temporal.payloads import RouteDecision

    return RouteDecision(
        model="groundwire-small",
        provider="groundwire",
        reason="test",
        estimated_cost_usd=0.0001,
        routed=True,
    )


@activity.defn(name="notify_approval")
async def notify_stub(run_id: str, tenant_id: str, agent_name: str, pending_action: dict) -> dict:
    return {"sent": False, "reason": "unconfigured"}


@activity.defn(name="execute_tool")
async def execute_stub(tool: str, params: dict) -> dict:
    return {"tool": tool, "params": params, "result": "executed"}


def _worker(client):
    return Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[AgentRunWorkflow],
        activities=[persist_stub, audit_stub, plan_stub, route_stub, notify_stub, execute_stub],
    )


async def _wait_status(handle, expected: str) -> None:
    for _ in range(50):
        if await handle.query(AgentRunWorkflow.status) == expected:
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"status never became {expected}")


async def test_approval_survives_worker_restart():
    run_input = _input()
    async with await WorkflowEnvironment.start_local() as env:
        async with _worker(env.client):
            handle = await env.client.start_workflow(
                AgentRunWorkflow.run,
                run_input,
                id=f"run-{run_input.run_id}",
                task_queue=TASK_QUEUE,
                execution_timeout=timedelta(seconds=60),
            )
            await _wait_status(handle, "awaiting_approval")
        async with _worker(env.client):
            await handle.signal(
                AgentRunWorkflow.approval_decision,
                ApprovalDecision(decision="approve", actor="tester"),
            )
            result = await handle.result()
            assert result["status"] == "completed"
