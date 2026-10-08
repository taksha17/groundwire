# RL/Eval Environment for Groundwire — Design Spec

**Date:** 2026-10-08
**Status:** Approved design (awaiting implementation plan)
**Owner:** taksha17

## 1. Purpose

Build one unified environment for stress-testing Groundwire in three modes:

1. **Bench** — load/stress benchmarking: latency, throughput, failure modes under approval storms, workflow floods, worker crashes. Output: metrics report.
2. **Eval** — agent-behavior scoring: synthetic agents run tasks through Groundwire; scored on respecting approval gates, audit completeness, malicious-action rejection. Output: pass/fail + 0–1 scorecard.
3. **Train** — RL training against Groundwire-as-environment via a Gymnasium-compatible API, with pluggable reward functions. Output: trained policy + reward curves.

## 2. Scenario families

All four of:

- **SRE incident storms** — floods of ops incidents requiring approvals, escalations, handoffs (builds on `examples/sre_incident_storm.py`)
- **Adversarial/malicious agents** — approval spam, fake identities, token replay, router hammering, mid-workflow worker crashes
- **Open-ended task datasets** — benchmark-style tasks of varying difficulty for agent-quality scoring
- **Synthetic scale floods** — pure N concurrent runs × M approval gates, saturating Temporal/Postgres/router to find breaking points

## 3. Architecture

New top-level `evals/` package (outputs gitignored, always on the media drive):

```
evals/
├── core/
│   ├── stack.py          # ephemeral compose stack lifecycle (up/down/logs)
│   ├── runner.py         # scenario executor: drives actors, collects results
│   ├── actors.py         # async actor base: normal / malicious / flood
│   ├── scoring.py        # scorecard: metrics + audit checks + behavior rules
│   └── env.py            # Gymnasium GroundwireEnv: reset/step via runner
├── scenarios/            # YAML scenario definitions (initial set below)
├── rewards/
│   ├── agent_policy.py   # task success − wasted steps − approval violations
│   └── ops_policy.py     # throughput + safety (Groundwire-side learner)
├── trainers/             # reference PPO / random-policy loops (PyTorch)
├── out/                  # gitignored: scorecards, RL curves, stack logs
└── compose.eval.yml      # extends docker-compose.yml; isolated ports + .data-eval/
```

Unified CLI: `evals run <scenario.yaml> --mode bench|eval|train`. Plus `evals doctor` (pre-flight) and `evals cleanup` (remove orphaned eval stacks).

### Components

- **`stack.py` — `EvalStack` context manager.** Creates `.data-eval/<run-id>/`, generates the eval compose override (project name `gw-eval-<uuid>`, API on `:18100`, all data paths under the repo/media drive), `compose up --wait`, health-checks API / Go router / Temporal, registers eval agents/keys, yields client handles. On exit: `compose down -v`, container logs to `out/<run-id>/logs/`. Never touches the dev stack. Ports checked free before up; refuses to start if a `gw-eval-*` project is already running.
- **`actors.py`.** Async actors, one per logical agent, each looping: pick task → `client.start_run` (optionally gated) → respond to approvals → complete. Variants: `NormalAgent` (realistic pacing), `MaliciousAgent` (token replay, fake IDs, spam approve/reject, kill-own-worker), `FloodActor` (fixed RPS `start_run`, no realism). Every action written to a trace file for scoring/replay.
- **`runner.py`.** Loads scenario YAML → instantiates actor mix (`count`, `arrival_rate`, `duration`, `seed`, `on_failure`) → runs to duration/episode end → snapshot: API `/v1/metrics`, `/v1/audit` dump, Postgres row counts, trace. Deterministic per seed.
- **`scoring.py`.** Two layers. *Infra metrics:* p50/p95/p99 latency of `start_run` and approvals, throughput, error rates, workflow backlog. *Behavior rules:* no run bypassed a gated approval; every completed run has a complete audit chain; malicious actions rejected and logged; etc. Eval mode → pass/fail + 0–1 score; bench mode → metrics only.
- **`env.py` — Gymnasium `GroundwireEnv`.** `reset(seed)` = cold stack up OR warm scenario reset (`--warm` flag; stack-up dominates episode time so training uses warm resets). `step(action)` maps a policy action (agent task choice, or ops decision: auto-approve/escalate/throttle/route) into actor/runner effects and returns `(obs, reward, terminated, truncated, info)`. Reward = pluggable callable from `rewards/` over per-step observations built from API/audit state.

### Data flow

`evals run scenarios/sre_storm.yaml --mode eval` → stack up → runner spawns actors per YAML → actors hit API / Go router / SDK → runner pulls metrics + audit + DB state → `scoring.py` → `out/<run-id>/scorecard.json` (+ trace + container logs) → stack down.

## 4. RL subjects

Two trainable policies sharing the env via pluggable rewards:

- **Agent policy** — task selection / tool use inside scenarios; reward = task success − wasted steps − approval-gate violations.
- **Groundwire ops policy** — when to auto-approve, escalate, throttle, route models; reward = throughput + safety.

Reference trainers in `trainers/` (PyTorch, PPO + random baseline) demonstrate both.

## 5. Error handling

- try/finally teardown — stack always comes down, logs always captured.
- Stack-up health-check timeout (default 120s) → clean failure naming the unhealthy service.
- Startup port/orphan checks refuse to stomp the dev stack; `evals cleanup` force-removes orphans.
- Actor exceptions captured in trace as events; `on_failure: respawn|abort` per scenario; episode aborts if >N% of actors die.
- Guardrails: root-disk free-space check at startup (warn <2GB), `max_runs` kill-switch, `--max-rates` caps.

## 6. Testing

- **Unit tests** in `tests/evals/` (`@pytest.mark.evals`): YAML schema, scoring rules vs fixture dumps, reward functions, port-conflict logic. No docker, runs in CI with main suite.
- **Integration test** (opt-in `@pytest.mark.evals_slow`): spin up real ephemeral stack, 30s low-RPS `scale_flood`, assert scorecard fields sane and stack fully torn down.
- **`evals doctor`**: docker reachable, ports free, disk space OK, cache env sourced.

## 7. Constraints

- Root drive nearly full (96% as of 2026-10-07): **all** caches, venvs, data, and outputs live on the media drive under the repo (`source scripts/env.sh`). Docker engine data-root currently misconfigured to root (`daemon.json` points at non-existent `Volume1` mount) — must be fixed before heavy training use; `evals doctor` should warn if `docker info` root dir is on `/`.
- Determinism: same seed → same scorecard.
- Actors test Groundwire through the public client SDK only (no internal imports) — evals measure what users experience.

## 8. Success criteria (v1)

1. `evals run scenarios/sre_storm.yaml --mode eval` completes deterministically with a valid scorecard using all four scenario families available as YAML.
2. `--mode train` with a random-policy trainer runs 10 warm-reset episodes without crashes and emits a reward curve.
3. Dev stack untouched throughout (data, ports, project names disjoint).
4. `evals doctor` catches the docker data-root-root-drive misconfiguration.

## 9. Build order

1. **Spike:** `stack.py` + minimal `scale_flood` scenario + minimal scoring — prove ephemeral lifecycle end-to-end. Labeled throwaway until proven.
2. Scenario DSL + runner + actors + scoring (bench + eval modes).
3. Gymnasium env + rewards + reference trainers (train mode).
4. Remaining scenario families; hardening (`doctor`, `cleanup`, guardrails); docs.
