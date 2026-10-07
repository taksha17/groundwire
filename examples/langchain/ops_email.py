#!/usr/bin/env python3
"""LangChain plans the email; Groundwire durably gates sending it.

Your chain owns the wording. Groundwire owns the pause, the crash-safe run,
and the paper trail. Approve the held send in the signal box.

    pip install -e .
    GROUNDWIRE_API_URL=http://localhost:18000 \\
    GROUNDWIRE_USERNAME=admin GROUNDWIRE_PASSWORD=admin \\
    python examples/langchain/ops_email.py

To use a real ChatOpenAI model instead of the offline stub:

    pip install -r examples/langchain/requirements.txt
    OPENAI_API_KEY=... python examples/langchain/ops_email.py --live
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from groundwire.client import client_from_env
from groundwire.handoff import canned_outage_email, ensure_ops_agent, start_gated_email

AGENT_NAME = "langchain-ops-email"


def plan_email(incident: str, *, live: bool = False) -> dict:
    if live:
        return _plan_with_langchain(incident)
    return canned_outage_email(incident)


def _plan_with_langchain(incident: str) -> dict:
    from langchain_core.output_parsers import JsonOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI

    prompt = ChatPromptTemplate.from_template(
        "Draft an operational outage email as JSON with keys to, subject, body. "
        "to must be ops@example.com. Incident: {incident}"
    )
    chain = prompt | ChatOpenAI(model="gpt-4o-mini", temperature=0) | JsonOutputParser()
    payload = chain.invoke({"incident": incident})
    if not isinstance(payload, dict):
        raise TypeError("LangChain chain did not return a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="LangChain → Groundwire gated send_email")
    parser.add_argument("--incident", default=os.environ.get("INCIDENT", "api latency"))
    parser.add_argument("--live", action="store_true", help="call LangChain + OpenAI instead of the canned draft")
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
    print(f"framework=langchain model_path={'live' if args.live else 'offline'}")
    print(f"run={held['id']} status={held['status']}")
    print(f"approve in the signal box: {args.dashboard}")
    return 0 if held["status"] == "awaiting_approval" else 1


if __name__ == "__main__":
    raise SystemExit(main())
