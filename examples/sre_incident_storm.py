#!/usr/bin/env python3
"""Stress the shipped control plane as an SRE incident night.

Burst of gated status-emails, mixed approve / reject / edit, then a worker
restart while runs still sit at danger. Against compose:

    GROUNDWIRE_API_URL=http://localhost:18000 \\
    GROUNDWIRE_USERNAME=admin GROUNDWIRE_PASSWORD=admin \\
    python examples/sre_incident_storm.py --count 48
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from groundwire.client import GroundwireClient, GroundwireError, client_from_env
from groundwire.handoff import canned_outage_email, ensure_ops_agent, start_gated_email

AGENT_NAME = "sre-incident-assist"

INCIDENTS = (
    "api latency us-east",
    "db failover primary",
    "disk full cache-03",
    "cert expiry edge",
    "k8s oom checkout",
    "queue lag payments",
    "5xx burst gateway",
    "replica lag analytics",
    "cdn origin timeout",
    "auth token stampede",
    "node notready pool-b",
    "slow query checkout",
)

HELD_EVENTS = {
    "run_started",
    "plan_completed",
    "model_routed",
    "approval_requested",
}
COMPLETED_EVENTS = HELD_EVENTS | {"approval_granted", "tool_executed", "run_completed"}
REJECTED_EVENTS = HELD_EVENTS | {"approval_rejected"}


def _login(username: str, password: str) -> GroundwireClient:
    client = client_from_env()
    if username != os.environ.get("GROUNDWIRE_USERNAME"):
        client.login_password(
            os.environ.get(
                "GROUNDWIRE_OIDC_TOKEN_URL",
                "http://localhost:8081/realms/groundwire/protocol/openid-connect/token",
            ),
            username,
            password,
        )
    return client


def _fire(client: GroundwireClient, agent_id: str, index: int) -> dict:
    label = f"{INCIDENTS[index % len(INCIDENTS)]} #{index + 1:03d}"
    run = start_gated_email(client, agent_id, canned_outage_email(label))
    held = client.wait_for_status(run["id"], ["awaiting_approval", "failed"], timeout=180)
    return {"index": index, "label": label, "run": held}


def _decide(client: GroundwireClient, item: dict, kind: str) -> dict:
    run_id = item["run"]["id"]
    params = dict(item["run"].get("pending_action", {}).get("params") or item["run"]["payload"])
    if kind == "reject":
        client.approve(run_id, "reject")
        expected = "rejected"
    elif kind == "edit":
        params["subject"] = f"SEV1: {item['label']}"
        client.approve(run_id, "edit", edited_params=params)
        expected = "completed"
    else:
        client.approve(run_id, "approve")
        expected = "completed"
    terminal = client.wait_for_status(run_id, ["completed", "rejected", "failed"], timeout=60)
    return {**item, "kind": kind, "expected": expected, "terminal": terminal}


def _restart_worker() -> None:
    result = subprocess.run(
        ["docker", "compose", "restart", "worker"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "worker restart failed")
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        probe = subprocess.run(
            ["docker", "compose", "ps", "-q", "worker"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if probe.stdout.strip():
            time.sleep(3)
            return
        time.sleep(0.5)
    raise RuntimeError("worker did not come back after restart")


def _wait_audit(client: GroundwireClient, run_id: str, wanted: set[str], timeout: float = 20.0) -> list[dict]:
    deadline = time.monotonic() + timeout
    latest: list[dict] = []
    while time.monotonic() < deadline:
        latest = client.run_audit(run_id)
        if wanted <= {row.get("event_type") for row in latest}:
            return latest
        time.sleep(0.2)
    return latest


def _report(rows: list[dict], held_after_crash: list[dict], metrics: dict, elapsed: float) -> int:
    statuses = Counter(row["terminal"]["status"] for row in rows)
    mismatches = [row for row in rows if row["terminal"]["status"] != row["expected"]]
    missing_audit = []
    actors = Counter()
    for row in rows:
        wanted = COMPLETED_EVENTS if row["expected"] == "completed" else REJECTED_EVENTS
        records = row.get("audit") or []
        got = {rec.get("event_type") for rec in records}
        if not wanted <= got:
            missing_audit.append((row["run"]["id"], sorted(wanted - got)))
        for rec in records:
            if rec.get("event_type") in {"approval_granted", "approval_rejected"}:
                actors[rec.get("actor") or ""] += 1

    print(f"storm_elapsed_s={elapsed:.1f}")
    print(f"fired={len(rows)} held_after_restart={len(held_after_crash)}")
    print(f"terminal={dict(statuses)}")
    print(f"actors={dict(actors)}")
    print(f"metrics={metrics}")
    if mismatches:
        print(f"STATUS_MISMATCH {len(mismatches)}")
        for row in mismatches[:8]:
            print(f"  {row['run']['id']} expected={row['expected']} got={row['terminal']['status']}")
    if missing_audit:
        print(f"AUDIT_GAPS {len(missing_audit)}")
        for run_id, missing in missing_audit[:8]:
            print(f"  {run_id} missing={missing}")
    lost = [row for row in held_after_crash if row["run"].get("status") not in {"awaiting_approval"}]
    ok = not mismatches and not lost and not missing_audit and len(held_after_crash) == len(rows)
    print("RESULT " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="SRE incident-assist storm against live Groundwire")
    parser.add_argument("--count", type=int, default=int(os.environ.get("STORM_COUNT", "48")))
    parser.add_argument("--workers", type=int, default=int(os.environ.get("STORM_WORKERS", "12")))
    parser.add_argument("--skip-restart", action="store_true")
    args = parser.parse_args()
    if args.count < 4:
        print("need at least 4 runs for mixed decisions", file=sys.stderr)
        return 2

    started = time.monotonic()
    admin = _login("admin", "admin")
    operator = _login("operator", "operator")
    agent = ensure_ops_agent(admin, AGENT_NAME)

    print(f"agent={agent['id']} name={AGENT_NAME} count={args.count}")
    fired: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(_fire, admin, agent["id"], i) for i in range(args.count)]
        for fut in as_completed(futs):
            item = fut.result()
            if item["run"]["status"] != "awaiting_approval":
                raise GroundwireError(f"run {item['run']['id']} never held: {item['run']['status']}")
            fired.append(item)
            print(f"held {item['run']['id']} {item['label']}")

    fired.sort(key=lambda item: item["index"])
    if not args.skip_restart:
        print("restarting worker while lamps sit at danger")
        _restart_worker()
        held_after = []
        for item in fired:
            again = admin.wait_for_status(item["run"]["id"], ["awaiting_approval", "failed"], timeout=45)
            held_after.append({**item, "run": again})
            if again["status"] != "awaiting_approval":
                raise GroundwireError(f"lost after restart: {item['run']['id']} {again['status']}")
        print(f"still_held={len(held_after)}")
    else:
        held_after = fired

    n = len(held_after)
    reject_n = max(1, n // 8)
    edit_n = max(1, n // 8)
    operator_n = max(1, n // 4)
    kinds: list[str] = (
        ["reject"] * reject_n
        + ["edit"] * edit_n
        + ["approve"] * (n - reject_n - edit_n)
    )
    decided: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = []
        for i, item in enumerate(held_after):
            kind = kinds[i]
            who = operator if i < operator_n and kind != "reject" else admin
            futs.append(pool.submit(_decide, who, item, kind))
        for fut in as_completed(futs):
            row = fut.result()
            wanted = COMPLETED_EVENTS if row["expected"] == "completed" else REJECTED_EVENTS
            row["audit"] = _wait_audit(admin, row["run"]["id"], wanted)
            decided.append(row)
            print(f"{row['kind']:7} {row['run']['id']} -> {row['terminal']['status']}")

    graphs = 0
    for row in decided[:5]:
        graph = admin.graph(row["run"]["id"])
        graphs += len(graph.get("nodes") or [])
    print(f"sample_graph_nodes={graphs}")
    csv_body = admin.audit(agent_id=agent["id"], format="json")
    print(f"audit_rows={len(csv_body) if isinstance(csv_body, list) else 'n/a'}")
    metrics = admin.metrics()
    admin.close()
    operator.close()
    return _report(decided, held_after, metrics, time.monotonic() - started)


if __name__ == "__main__":
    raise SystemExit(main())
