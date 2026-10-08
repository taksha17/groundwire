"""Live resource-constrained stress against compose.

The opposite corner from extreme_concurrency: only 4 worker threads sharing
one client whose httpx pool is deliberately starved (4 connections, 2
keep-alive). Simulates a small pod where the API is hammered through a
bottleneck, then hammers the read path while runs sit held, then drains.

    source test_venv/bin/activate
    python -m pytest tests/stress_scenarios/comprehensive/resource_constrained_stress.py::ResourceConstrainedStressTests::test_resource_constrained_load -v --tb=short
"""

from __future__ import annotations

import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

os.environ.setdefault("GROUNDWIRE_API_URL", "http://127.0.0.1:18000")
os.environ.setdefault("GROUNDWIRE_USERNAME", "admin")
os.environ.setdefault("GROUNDWIRE_PASSWORD", "admin")

from groundwire.client import GroundwireClient, GroundwireError, client_from_env
from groundwire.handoff import canned_outage_email, ensure_ops_agent, start_gated_email

AGENT_NAME = "resource-bottleneck-assist"
WORKFLOW_COUNT = 300
START_WORKERS = 4
WAVE_SIZE = 50
WAVE_PAUSE_S = 1.0
HOLD_TIMEOUT = 900.0
TERMINAL = ("completed", "rejected", "failed")
POOL_LIMITS = httpx.Limits(max_connections=4, max_keepalive_connections=2)
POOL_TIMEOUT = 10.0


def _starved_client() -> GroundwireClient:
    """client_from_env() credentials, but with a deliberately tiny httpx pool."""
    client = client_from_env()
    token = client._token  # keep auth already negotiated by client_from_env
    return GroundwireClient(
        client.base_url,
        token=token,
        client=httpx.Client(
            base_url=client.base_url,
            limits=POOL_LIMITS,
            timeout=POOL_TIMEOUT,
        ),
    )


class ResourceConstrainedStressTests(unittest.TestCase):
    def test_resource_constrained_load(self) -> None:
        client = _starved_client()
        self.addCleanup(client.close)
        agent = ensure_ops_agent(client, AGENT_NAME)
        agent_id = agent["id"]

        # --- Phase 1: bottlenecked start, bursty waves ---------------------
        started = time.monotonic()
        held: list[str] = []
        failed: list[str] = []

        def fire(index: int) -> tuple[str, str]:
            run = start_gated_email(
                client,
                agent_id,
                canned_outage_email(f"bottleneck #{index + 1:04d}"),
            )
            latest = client.wait_for_status(
                run["id"], ["awaiting_approval", "failed"], timeout=HOLD_TIMEOUT
            )
            return run["id"], str(latest["status"])

        def fire_wave(offset: int) -> list[tuple[str, str]]:
            results: list[tuple[str, str]] = []
            with ThreadPoolExecutor(max_workers=START_WORKERS) as pool:
                futs = [
                    pool.submit(fire, i)
                    for i in range(offset, min(offset + WAVE_SIZE, WORKFLOW_COUNT))
                ]
                for fut in as_completed(futs):
                    results.append(fut.result())
            return results

        for wave in range(0, WORKFLOW_COUNT, WAVE_SIZE):
            for run_id, status in fire_wave(wave):
                if status == "awaiting_approval":
                    held.append(run_id)
                else:
                    failed.append(f"{run_id}:{status}")
            if wave + WAVE_SIZE < WORKFLOW_COUNT:
                time.sleep(WAVE_PAUSE_S)
            print(f"progress {min(wave + WAVE_SIZE, WORKFLOW_COUNT)}/{WORKFLOW_COUNT} "
                  f"held={len(held)} failed={len(failed)}")

        self.assertEqual(failed, [])
        self.assertEqual(len(held), WORKFLOW_COUNT)
        self.assertEqual(len(set(held)), WORKFLOW_COUNT)

        # --- Phase 2: read-path contention through the same tiny pool ------
        read_errors: list[str] = []

        def read_probe(index: int) -> None:
            run_id = held[index % len(held)]
            fetched = client.get_run(run_id)
            assert fetched["id"] == run_id, f"get_run returned wrong id {fetched['id']}"
            client.list_runs(status="awaiting_approval")
            client.run_audit(run_id)
            client.metrics()

        with ThreadPoolExecutor(max_workers=START_WORKERS) as pool:
            futs = [pool.submit(read_probe, i) for i in range(WORKFLOW_COUNT)]
            for i, fut in enumerate(as_completed(futs), start=1):
                try:
                    fut.result()
                except (GroundwireError, httpx.HTTPError, AssertionError) as exc:
                    read_errors.append(str(exc))
                if i % 100 == 0:
                    print(f"read progress {i}/{WORKFLOW_COUNT} errors={len(read_errors)}")

        self.assertEqual(read_errors, [])

        # --- Phase 3: bottlenecked drain ------------------------------------
        n = len(held)
        reject_n = max(1, n // 8)
        edit_n = max(1, n // 8)
        kinds = ["reject"] * reject_n + ["edit"] * edit_n + ["approve"] * (n - reject_n - edit_n)
        errors: list[str] = []
        terminal: list[tuple[str, str, str]] = []

        def pull(run_id: str, kind: str) -> tuple[str, str, str]:
            if kind == "reject":
                client.approve(run_id, "reject")
                expected = "rejected"
            elif kind == "edit":
                run = client.get_run(run_id)
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
            futs = [pool.submit(pull, rid, kind) for rid, kind in zip(held, kinds, strict=True)]
            for i, fut in enumerate(as_completed(futs), start=1):
                try:
                    terminal.append(fut.result())
                except (GroundwireError, httpx.HTTPError) as exc:
                    errors.append(str(exc))
                if i % 50 == 0:
                    print(f"drain progress {i}/{n} decided={len(terminal)} errors={len(errors)}")

        mismatches = [row for row in terminal if row[1] != row[2]]
        failed_terms = [row for row in terminal if row[2] == "failed"]
        elapsed = time.monotonic() - started
        print(
            f"bottlenecked workflows={WORKFLOW_COUNT} elapsed_s={elapsed:.1f} "
            f"rate={WORKFLOW_COUNT / elapsed:.1f}/s "
            f"mismatches={len(mismatches)} errors={len(errors)}"
        )
        self.assertEqual(errors, [])
        self.assertEqual(mismatches, [])
        self.assertEqual(failed_terms, [])
        self.assertEqual(len(terminal), n)

        leftover = [
            run
            for run in client.list_runs(status="awaiting_approval")
            if run.get("agent_name") == AGENT_NAME
        ]
        self.assertEqual(leftover, [])
