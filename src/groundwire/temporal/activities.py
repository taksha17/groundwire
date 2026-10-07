import re
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from temporalio import activity

from groundwire.models import AuditRecord, Run
from groundwire.settings import get_settings
from groundwire.temporal.payloads import PlanResult, RouteDecision, RunWorkflowInput, ToolCall

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


_HEAVY = ("analyze", "reason", "plan", "summarize", "rag", "research", "write a long")


def fallback_route(task: str, prompt: str) -> RouteDecision:
    tokens = max(32, len(prompt) // 4)
    blob = f"{task} {prompt}".lower()
    large = tokens > 400 or any(re.search(rf"\b{re.escape(word)}\b", blob) for word in _HEAVY)
    out_tokens = min(200, tokens // 2)
    if large:
        cost = (tokens * 2.50 + out_tokens * 10.0) / 1_000_000
        return RouteDecision(
            model="groundwire-large",
            provider="groundwire",
            reason="long or reasoning-shaped prompt; send it to the larger model",
            estimated_cost_usd=round(cost, 6),
            input_tokens=tokens,
            output_tokens=out_tokens,
            routed=False,
        )
    cost = (tokens * 0.15 + out_tokens * 0.60) / 1_000_000
    return RouteDecision(
        model="groundwire-small",
        provider="groundwire",
        reason="short deterministic tool call; keep it on the small model",
        estimated_cost_usd=round(cost, 6),
        input_tokens=tokens,
        output_tokens=out_tokens,
        routed=False,
    )


@activity.defn
async def route_model(task: str, prompt: str) -> RouteDecision:
    settings = get_settings()
    if not settings.router_url:
        return fallback_route(task, prompt)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{settings.router_url.rstrip('/')}/v1/route",
                json={"task": task, "prompt": prompt},
            )
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError:
        return fallback_route(task, prompt)
    return RouteDecision(
        model=str(body.get("model") or "groundwire-small"),
        provider=str(body.get("provider") or "groundwire"),
        reason=str(body.get("reason") or ""),
        estimated_cost_usd=float(body.get("estimated_cost_usd") or 0),
        input_tokens=int(body.get("input_tokens") or 0),
        output_tokens=int(body.get("output_tokens") or 0),
        routed=bool(body.get("routed")),
    )
