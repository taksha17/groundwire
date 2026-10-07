import asyncio
from datetime import timedelta
from uuid import uuid4

from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from groundwire.temporal.payloads import ApprovalDecision, PlanResult, RunWorkflowInput, ToolCall
from groundwire.temporal.workflows import AgentRunWorkflow

TASK_QUEUE = "test-agent-runs"
executed: list[dict] = []
notified: list[dict] = []


def _input() -> RunWorkflowInput:
    run_id = str(uuid4())
    return RunWorkflowInput(
        run_id=run_id,
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
            ToolCall(
                tool="send_email",
                params=input.payload,
                rationale="Notify ops of the outage",
            )
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
    notified.append(
        {
            "run_id": run_id,
            "tenant_id": tenant_id,
            "agent_name": agent_name,
            "pending_action": pending_action,
        }
    )
    return {"sent": True, "status_code": 200}


@activity.defn(name="execute_tool")
async def execute_stub(tool: str, params: dict) -> dict:
    executed.append({"tool": tool, "params": params})
    return {"tool": tool, "params": params, "result": "executed"}


async def _wait_status(handle, expected: str) -> None:
    for _ in range(50):
        if await handle.query(AgentRunWorkflow.status) == expected:
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"status never became {expected}")


async def test_workflow_pauses_until_approval_then_executes():
    executed.clear()
    notified.clear()
    run_input = _input()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[AgentRunWorkflow],
            activities=[persist_stub, audit_stub, plan_stub, route_stub, notify_stub, execute_stub],
        ):
            handle = await env.client.start_workflow(
                AgentRunWorkflow.run,
                run_input,
                id=f"run-{run_input.run_id}",
                task_queue=TASK_QUEUE,
                execution_timeout=timedelta(seconds=30),
            )
            await _wait_status(handle, "awaiting_approval")
            pending = await handle.query(AgentRunWorkflow.pending_action)
            assert pending["model"] == "groundwire-small"
            assert executed == []
            assert notified[0]["run_id"] == run_input.run_id
            assert notified[0]["pending_action"]["tool"] == "send_email"
            await handle.signal(
                AgentRunWorkflow.approval_decision,
                ApprovalDecision(decision="approve", actor="tester"),
            )
            result = await handle.result()
            assert result["status"] == "completed"
            assert executed == [
                {
                    "tool": "send_email",
                    "params": run_input.payload,
                }
            ]


async def test_workflow_reject_does_not_execute_tool():
    executed.clear()
    run_input = _input()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[AgentRunWorkflow],
            activities=[persist_stub, audit_stub, plan_stub, route_stub, notify_stub, execute_stub],
        ):
            handle = await env.client.start_workflow(
                AgentRunWorkflow.run,
                run_input,
                id=f"run-{run_input.run_id}",
                task_queue=TASK_QUEUE,
                execution_timeout=timedelta(seconds=30),
            )
            await _wait_status(handle, "awaiting_approval")
            await handle.signal(
                AgentRunWorkflow.approval_decision,
                ApprovalDecision(decision="reject", actor="tester"),
            )
            result = await handle.result()
            assert result["status"] == "rejected"
            assert executed == []


async def test_workflow_edit_and_approve_uses_edited_params():
    executed.clear()
    run_input = _input()
    edited = {"to": "legal@example.com", "subject": "Outage", "body": "x"}
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[AgentRunWorkflow],
            activities=[persist_stub, audit_stub, plan_stub, route_stub, notify_stub, execute_stub],
        ):
            handle = await env.client.start_workflow(
                AgentRunWorkflow.run,
                run_input,
                id=f"run-{run_input.run_id}",
                task_queue=TASK_QUEUE,
                execution_timeout=timedelta(seconds=30),
            )
            await _wait_status(handle, "awaiting_approval")
            await handle.signal(
                AgentRunWorkflow.approval_decision,
                ApprovalDecision(decision="edit", edited_params=edited, actor="tester"),
            )
            result = await handle.result()
            assert result["status"] == "completed"
            assert executed == [{"tool": "send_email", "params": edited}]
