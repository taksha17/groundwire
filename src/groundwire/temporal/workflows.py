from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

from groundwire.temporal.payloads import (
    ApprovalDecision,
    PlanResult,
    RouteDecision,
    RunWorkflowInput,
)


@workflow.defn
class AgentRunWorkflow:
    def __init__(self) -> None:
        self._decision: ApprovalDecision | None = None
        self._status = "planning"
        self._pending_action: dict | None = None

    @workflow.run
    async def run(self, input: RunWorkflowInput) -> dict:
        try:
            await self._persist(input.run_id, "planning", "plan_run", None)
            await self._audit(input, "run_started", "system", {"agent": input.agent_name})

            plan = await workflow.execute_activity(
                "plan_run",
                input,
                start_to_close_timeout=timedelta(seconds=30),
                result_type=PlanResult,
            )
            await self._audit(input, "plan_completed", "system", {"summary": plan.summary})

            last_result = None
            for call in plan.tool_calls:
                params = call.params
                route: RouteDecision | None = None
                if workflow.patched("model-router"):
                    route = await workflow.execute_activity(
                        "route_model",
                        args=[call.tool, f"{call.rationale}\n{params}"],
                        start_to_close_timeout=timedelta(seconds=15),
                        result_type=RouteDecision,
                    )
                    await self._audit(
                        input,
                        "model_routed",
                        "router",
                        {
                            "tool": call.tool,
                            "model": route.model,
                            "provider": route.provider,
                            "reason": route.reason,
                            "estimated_cost_usd": route.estimated_cost_usd,
                            "input_tokens": route.input_tokens,
                            "output_tokens": route.output_tokens,
                            "routed": route.routed,
                        },
                    )
                requires_approval = call.tool in (input.approval_policy.get("require_approval_for") or [])
                if requires_approval:
                    self._pending_action = {
                        "tool": call.tool,
                        "params": params,
                        "rationale": call.rationale,
                    }
                    if route is not None:
                        self._pending_action["model"] = route.model
                        self._pending_action["estimated_cost_usd"] = route.estimated_cost_usd
                    self._status = "awaiting_approval"
                    await self._persist(
                        input.run_id, self._status, "approval_gate", self._pending_action
                    )
                    await self._audit(input, "approval_requested", "system", self._pending_action)
                    if workflow.patched("approval-webhook"):
                        ping = await workflow.execute_activity(
                            "notify_approval",
                            args=[
                                input.run_id,
                                input.tenant_id,
                                input.agent_name,
                                self._pending_action,
                            ],
                            start_to_close_timeout=timedelta(seconds=12),
                        )
                        await self._audit(input, "approval_notified", "system", ping)
                    timed_out = False
                    if workflow.patched("approval-timeout"):
                        timeout_seconds = int(input.approval_policy.get("timeout_seconds") or 0)
                        if timeout_seconds > 0:
                            try:
                                await workflow.wait_condition(
                                    lambda: self._decision is not None,
                                    timeout=timedelta(seconds=timeout_seconds),
                                )
                            except TimeoutError:
                                timed_out = True
                        else:
                            await workflow.wait_condition(lambda: self._decision is not None)
                    else:
                        await workflow.wait_condition(lambda: self._decision is not None)
                    if timed_out:
                        self._status = "rejected"
                        await self._persist(
                            input.run_id, self._status, "approval_gate", self._pending_action
                        )
                        await self._audit(
                            input,
                            "approval_expired",
                            "system",
                            {"tool": call.tool, "timeout_seconds": timeout_seconds},
                        )
                        return {"status": "rejected", "reason": "approval_timeout"}
                    decision = self._decision
                    assert decision is not None
                    if decision.decision == "reject":
                        self._status = "rejected"
                        await self._persist(
                            input.run_id, self._status, "approval_gate", self._pending_action
                        )
                        await self._audit(
                            input, "approval_rejected", decision.actor, {"tool": call.tool}
                        )
                        return {"status": "rejected"}
                    if decision.decision == "edit" and decision.edited_params is not None:
                        params = decision.edited_params
                    await self._audit(
                        input,
                        "approval_granted",
                        decision.actor,
                        {"tool": call.tool, "params": params, "decision": decision.decision},
                    )

                self._status = "executing"
                self._pending_action = None
                await self._persist(input.run_id, self._status, call.tool, None)
                last_result = await workflow.execute_activity(
                    "execute_tool",
                    args=[call.tool, params],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )
                await self._audit(input, "tool_executed", "system", last_result)

            self._status = "completed"
            await self._persist(input.run_id, self._status, None, None)
            await self._audit(input, "run_completed", "system", {"result": last_result})
            return {"status": "completed", "result": last_result}
        except ActivityError as exc:
            self._status = "failed"
            await self._persist(input.run_id, self._status, None, {"error": str(exc)})
            await self._audit(input, "run_failed", "system", {"error": str(exc)})
            return {"status": "failed", "error": str(exc)}

    @workflow.signal
    def approval_decision(self, decision: ApprovalDecision) -> None:
        self._decision = decision

    @workflow.query
    def status(self) -> str:
        return self._status

    @workflow.query
    def pending_action(self) -> dict | None:
        return self._pending_action

    async def _persist(
        self,
        run_id: str,
        status: str,
        current_step: str | None,
        pending_action: dict | None,
    ) -> None:
        await workflow.execute_activity(
            "persist_run_progress",
            args=[run_id, status, current_step, pending_action],
            start_to_close_timeout=timedelta(seconds=10),
        )

    async def _audit(self, input: RunWorkflowInput, event_type: str, actor: str, payload: dict) -> None:
        await workflow.execute_activity(
            "write_audit",
            args=[input.run_id, input.tenant_id, event_type, actor, payload],
            start_to_close_timeout=timedelta(seconds=10),
        )
