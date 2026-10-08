"""Live extreme-concurrency stress against compose.

Starts 1_000 gated incident runs at once and asserts every workflow
reaches awaiting_approval. Not collected as a fast unit test — run it
explicitly:

    source test_venv/bin/activate
    python -m pytest tests/stress_scenarios/comprehensive/extreme_concurrency_stress.py::ExtremeConcurrencyStressTests::test_extreme_concurrency_1000_workflows -v --tb=short
"""

from __future__ import annotations

import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed

os.environ.setdefault("GROUNDWIRE_API_URL", "http://127.0.0.1:18000")
os.environ.setdefault("GROUNDWIRE_USERNAME", "admin")
os.environ.setdefault("GROUNDWIRE_PASSWORD", "admin")

from groundwire.client import GroundwireError, client_from_env
from groundwire.handoff import canned_outage_email, ensure_ops_agent, start_gated_email

AGENT_NAME = "sre-incident-assist"
WORKFLOW_COUNT = 1000
START_WORKERS = 32
HOLD_TIMEOUT = 600.0
TERMINAL = ("completed", "rejected", "failed")


class ExtremeConcurrencyStressTests(unittest.TestCase):
    def test_extreme_concurrency_1000_workflows(self) -> None:
        client = client_from_env()
        self.addCleanup(client.close)
        agent = ensure_ops_agent(client, AGENT_NAME)
        started = time.monotonic()
        held: list[str] = []
        failed: list[str] = []

        def fire(index: int) -> tuple[str, str]:
            run = start_gated_email(
                client,
                agent["id"],
                canned_outage_email(f"extreme concurrency #{index + 1:04d}"),
            )
            latest = client.wait_for_status(
                run["id"],
                ["awaiting_approval", "failed"],
                timeout=HOLD_TIMEOUT,
            )
            return run["id"], str(latest["status"])

        with ThreadPoolExecutor(max_workers=START_WORKERS) as pool:
            futs = [pool.submit(fire, i) for i in range(WORKFLOW_COUNT)]
            for i, fut in enumerate(as_completed(futs), start=1):
                try:
                    run_id, status = fut.result()
                except GroundwireError as exc:
                    failed.append(str(exc))
                    continue
                if status == "awaiting_approval":
                    held.append(run_id)
                else:
                    failed.append(f"{run_id}:{status}")
                if i % 100 == 0:
                    print(f"progress {i}/{WORKFLOW_COUNT} held={len(held)} failed={len(failed)}")

        elapsed = time.monotonic() - started
        print(
            f"extreme_concurrency workflows={WORKFLOW_COUNT} held={len(held)} "
            f"failed={len(failed)} elapsed_s={elapsed:.1f} "
            f"rate={WORKFLOW_COUNT / elapsed:.1f}/s"
        )
        self.assertEqual(failed, [])
        self.assertEqual(len(held), WORKFLOW_COUNT)
        self.assertEqual(len(set(held)), WORKFLOW_COUNT)

    def test_extreme_concurrency_1000_approvals(self) -> None:
        """On-call clears a 1_000-alert board: mixed levers, all in parallel."""
        client = client_from_env()
        self.addCleanup(client.close)
        held = [
            run
            for run in client.list_runs(status="awaiting_approval")
            if run.get("agent_name") == AGENT_NAME
        ]
        self.assertGreaterEqual(
            len(held),
            900,
            "run test_extreme_concurrency_1000_workflows first so a held backlog exists",
        )
        n = len(held)
        reject_n = max(1, n // 8)
        edit_n = max(1, n // 8)
        kinds = ["reject"] * reject_n + ["edit"] * edit_n + ["approve"] * (n - reject_n - edit_n)
        started = time.monotonic()
        terminal: list[tuple[str, str, str]] = []
        errors: list[str] = []

        def pull(run: dict, kind: str) -> tuple[str, str, str]:
            run_id = str(run["id"])
            if kind == "reject":
                client.approve(run_id, "reject")
                expected = "rejected"
            elif kind == "edit":
                params = dict((run.get("pending_action") or {}).get("params") or run["payload"])
                params["subject"] = f"SEV1 {params.get('subject', 'page')}"
                client.approve(run_id, "edit", edited_params=params)
                expected = "completed"
            else:
                client.approve(run_id, "approve")
                expected = "completed"
            latest = client.wait_for_status(run_id, TERMINAL, timeout=HOLD_TIMEOUT)
            return run_id, expected, str(latest["status"])

        with ThreadPoolExecutor(max_workers=START_WORKERS) as pool:
            futs = [pool.submit(pull, run, kind) for run, kind in zip(held, kinds, strict=True)]
            for i, fut in enumerate(as_completed(futs), start=1):
                try:
                    run_id, expected, status = fut.result()
                except GroundwireError as exc:
                    errors.append(str(exc))
                    continue
                terminal.append((run_id, expected, status))
                if i % 100 == 0:
                    print(f"progress {i}/{n} decided={len(terminal)} errors={len(errors)}")

        elapsed = time.monotonic() - started
        mismatches = [row for row in terminal if row[1] != row[2]]
        failed = [row for row in terminal if row[2] == "failed"]
        print(
            f"extreme_approvals backlog={n} decided={len(terminal)} "
            f"mismatches={len(mismatches)} errors={len(errors)} "
            f"elapsed_s={elapsed:.1f} rate={n / elapsed:.1f}/s"
        )
        self.assertEqual(errors, [])
        self.assertEqual(mismatches, [])
        self.assertEqual(failed, [])
        self.assertEqual(len(terminal), n)
        leftover = [
            run
            for run in client.list_runs(status="awaiting_approval")
            if run.get("agent_name") == AGENT_NAME
        ]
        self.assertEqual(leftover, [])
