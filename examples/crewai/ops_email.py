#!/usr/bin/env python3
"""CrewAI plans the email; Groundwire durably gates sending it.

The crew writes the page. Groundwire holds send_email at danger until a human
pulls the lever. Same contract as the LangChain example — different planner.

    pip install -e .
    GROUNDWIRE_API_URL=http://localhost:18000 \\
    GROUNDWIRE_USERNAME=admin GROUNDWIRE_PASSWORD=admin \\
    python examples/crewai/ops_email.py

To run a real CrewAI crew:

    pip install -r examples/crewai/requirements.txt
    OPENAI_API_KEY=... python examples/crewai/ops_email.py --live
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from groundwire.client import client_from_env
from groundwire.handoff import canned_outage_email, ensure_ops_agent, start_gated_email

AGENT_NAME = "crewai-ops-email"


def plan_email(incident: str, *, live: bool = False) -> dict:
    if live:
        return _plan_with_crewai(incident)
    return canned_outage_email(incident)


def _plan_with_crewai(incident: str) -> dict:
    from crewai import Agent, Crew, Task

    writer = Agent(
        role="On-call scribe",
        goal="Draft a short outage page for human approval before send",
        backstory="You write terse ops emails. You never send them yourself.",
        verbose=False,
        allow_delegation=False,
    )
    task = Task(
        description=(
            "Draft an operational outage email as JSON with keys to, subject, body. "
            f"to must be ops@example.com. Incident: {incident}"
        ),
        expected_output='{"to": "...", "subject": "...", "body": "..."}',
        agent=writer,
    )
    result = Crew(agents=[writer], tasks=[task]).kickoff()
    raw = result.raw if hasattr(result, "raw") else str(result)
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise TypeError("CrewAI crew did not return a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="CrewAI → Groundwire gated send_email")
    parser.add_argument("--incident", default=os.environ.get("INCIDENT", "api latency"))
    parser.add_argument("--live", action="store_true", help="call CrewAI + an LLM instead of the canned draft")
    parser.add_argument(
        "--dashboard",
        default=os.environ.get("GROUNDWIRE_DASHBOARD_URL", "http://localhost:4200"),
    )
    args = parser.parse_args()
    payload = plan_email(args.incident, live=args.live)
    with client_from_env() as client:
        agent = ensure_ops_agent(client, AGENT_NAME)
        run = start_gated_email(client, agent["id"], payload)
        held = client.wait_for_status(run["id"], ["awaiting_approval", "failed"], timeout=45)
    print(f"framework=crewai model_path={'live' if args.live else 'offline'}")
    print(f"run={held['id']} status={held['status']}")
    print(f"approve in the signal box: {args.dashboard}")
    return 0 if held["status"] == "awaiting_approval" else 1


if __name__ == "__main__":
    raise SystemExit(main())
