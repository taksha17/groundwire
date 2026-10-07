from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from groundwire.client import GroundwireClient

OPS_APPROVAL_POLICY = {"require_approval_for": ["send_email"]}


def canned_outage_email(incident: str, *, to: str = "ops@example.com") -> dict[str, str]:
    label = incident.strip() or "unspecified incident"
    return {
        "to": to,
        "subject": f"Outage: {label}",
        "body": f"Please page on-call.\n\nIncident: {label}\n",
    }


def ensure_ops_agent(client: GroundwireClient, name: str) -> dict:
    for agent in client.list_agents():
        if agent.get("name") == name:
            return agent
    return client.register_agent(
        name=name,
        allowed_tools=["send_email"],
        approval_policy=OPS_APPROVAL_POLICY,
    )


def start_gated_email(client: GroundwireClient, agent_id: str, payload: Mapping[str, Any]) -> dict:
    missing = [key for key in ("to", "subject", "body") if key not in payload]
    if missing:
        raise ValueError(f"email payload missing {missing}")
    return client.start_run(agent_id, payload)
