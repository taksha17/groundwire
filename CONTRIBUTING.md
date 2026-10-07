# Contributing to Groundwire

The pause is the product. Changes should make durability, approval, or the audit trail clearer — not add another agent framework.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Go 1.22 is enough for the router (`cd router && go test`). Dashboard: Node 22, `cd dashboard && npm ci && npm run build`.

Keep caches and data on this repo's volume, not on `/`:

- Postgres bind: `./.data/postgres`
- pytest / Go: `TMPDIR`, `GOCACHE`, `GOMODCACHE` under `./.data/`
- Host-build `router/groundwire-router` (`CGO_ENABLED=0`) so compose never pulls a `golang` image
- Host-build the dashboard dist; compose uses `dashboard/Dockerfile.runtime`

Do not delete unrelated Docker images on the host.

## Tests

`pytest -q` is the bar for Python. Add a test with the behavior, not after it. Workflow and crash tests live in `tests/test_workflow.py` and `tests/test_worker_crash.py` — if you change `AgentRunWorkflow`, use `workflow.patched(...)` so in-flight runs keep replaying.

Router: `go test` in `router/`.

Do not add LangChain or CrewAI to the core extra. Example live paths are optional (`examples/*/requirements.txt`).

## What belongs where

| Path | Own this |
|---|---|
| `src/groundwire/` | Control plane, worker, client |
| `router/` | Model pick + cost |
| `dashboard/` | Operator signal box |
| `examples/` | Bring-your-own-framework samples |
| `DESIGN.md` | Visual world — enamel plate, lamps, brass levers |

Do not restyle the dashboard into a generic admin theme. If the operator surface changes, it still has to read as a railway signal box (`DESIGN.md`).

## Pull requests

- Small, one milestone-shaped change.
- Apache 2.0 only; no Highcharts or other GPL/commercial UI kits.
- No secrets, `.env`, or tokens in commits.
- Describe why, and how you verified (pytest, compose, or the box in a browser).

Issues are the discussion channel for now. GitHub Discussions can be enabled on the repo when you want a wider public square.
