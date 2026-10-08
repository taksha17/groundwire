<div align="center">

# Groundwire

### Durable, governed infrastructure for AI agents

**The pause is the product.** Your agent framework decides *what* to do — Groundwire guarantees it survives crashes, stops for a human when it matters, and leaves a paper trail.

[![Status](https://img.shields.io/badge/release-v1.0%20%E2%80%94%20Public%20launch-green)](Groundwire_PRD.md)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-%E2%89%A53.12-blue)]()
[![Angular](https://img.shields.io/badge/dashboard-Angular%2019-red)]()
[![Durable](https://img.shields.io/badge/execution-Temporal-7353ba)]()
[![Self-host](https://img.shields.io/badge/self--host-docker%20compose%20%C2%B7%20%240-success)]()

</div>

---

## The problem

AI agents are great in demos and fragile in production. If you've tried to run one against real operational systems, you've hit this wall:

- **💥 Long-running agents die silently.** A task that calls five tools and waits on a human can take minutes to hours. One restart, and most frameworks lose everything.
- **🙋 "Human-in-the-loop" is bolted on.** An `input()` call or a fire-and-forget webhook isn't an approval gate. What happens when the approver doesn't respond for three days?
- **📜 No real audit trail.** When an agent sends an email or calls a paid API — *who authorized this, under what policy, and why?* In any regulated context, "we don't know" is a showstopper.
- **🔑 Identity is an afterthought.** Without enterprise SSO, "which human is accountable?" is often unanswerable.

Existing tools each solve a slice: **LangGraph / CrewAI** are great at agent *logic*, weak on durability and governance. **Temporal / n8n / Windmill** are great at durable workflows, but not built around agent primitives. **Groundwire combines them — purpose-built for agents.**

## What Groundwire is

An open-source **control plane** that sits *underneath* your agent framework as the execution and governance layer. You keep your agent logic; Groundwire guarantees it runs reliably, safely, and audibly.

| Capability | Status | What it means |
|---|---|---|
| ⏳ **Durable execution** | ✅ shipped | Every run is a Temporal workflow. Crash mid-run, restart the worker, redeploy — the run resumes where it left off. Zero state loss (covered by `tests/test_worker_crash.py`). |
| ✋ **First-class approval gates** | ✅ shipped | Any step can require human approval. The workflow durably pauses on a Temporal signal — minutes or weeks — until someone approves, rejects, or edits-and-approves. |
| 🕸️ **Operator dashboard** | ✅ shipped | An Angular "railway signal box": live run strip with spectacle lamps, a D3 execution DAG, and brass levers for Approve / Reject right on the held node. |
| 📖 **Audit records** | ✅ shipped | Queryable occurrence book: filter by agent, tenant, date, outcome; export JSON/CSV; per-run timeline. |
| 🔐 **Enterprise identity** | ✅ shipped | OIDC via Keycloak. Tenant-scoped RBAC: admin registers agents, operator approves. |
| 🧠 **Model routing** | ✅ shipped | Go service picks `groundwire-small` vs `groundwire-large` per tool call, logs the decision, and lights the cost gauge. |
| 🧩 **Example agents** | ✅ shipped | LangChain and CrewAI draft an ops email; Groundwire holds `send_email` until a human approves. |

## Quick start

```bash
git clone https://github.com/taksha17/groundwire.git
cd groundwire
docker compose up --build
```

One command brings up the whole stateful backend — **Postgres, Keycloak, Temporal (+ UI), the Go model-router, the FastAPI control plane, the durable worker, the dashboard, and the public page**. First boot takes a minute while Temporal auto-setup and Keycloak import the demo realm.

Host-build the router binary first (keeps a `golang` image off `/`):

```bash
GOCACHE="$PWD/.data/gocache" GOMODCACHE="$PWD/.data/gomodcache" \
  CGO_ENABLED=0 go build -o router/groundwire-router ./router
```

The dashboard image copies a host `ng build` so a Node image never lands on `/`. From `dashboard/`: `npm ci && npm run build`.

| Surface | URL |
|---|---|
| 🌐 Public page | http://localhost:4300 |
| 🖥️ Dashboard (signal box) | http://localhost:4200 |
| 🔌 Control plane API | http://localhost:8000 |
| 🧠 Model router | http://localhost:8090 |
| 🪪 Keycloak | http://localhost:8081 (realm `groundwire`) |
| 🔭 Temporal UI | http://localhost:8088 |

Sign in to the box as **admin / admin** (can register agents) or **operator / operator** (can approve, cannot register). Those passwords are a first-boot secret. Before anyone else can open the box, change them in the Keycloak admin console at http://localhost:8081 (master user `admin` / `admin`, realm `groundwire`, then Users → Credentials). Published ports bind to `127.0.0.1` only. Compose data lives in `./.data` on this volume, not on `/`.

Ports taken? `GROUNDWIRE_API_PORT=18000 GROUNDWIRE_DASHBOARD_PORT=4201 GROUNDWIRE_SITE_PORT=4301 docker compose up --build`

### Try it: a gated agent in 60 seconds

**From the dashboard** — open the signal box, click **Set a route**. That registers the demo agent and starts a `send_email` run. When the lamp goes red (`awaiting_approval`), pull **Approve** or **Reject** directly on the DAG node. Now for the fun part: `docker compose restart worker` while it's held — the run is still there, waiting. *That's the point.*

Want a ping instead of watching the box? Point the worker at a webhook. The run still pauses if the hook is down.

```bash
python examples/webhook_sink.py
APPROVAL_WEBHOOK_URL=http://host.docker.internal:8091 docker compose up -d worker
```

The POST body is JSON: `event`, `run_id`, `agent_name`, `tool`, `pending_action`, `dashboard_url`. Optional `APPROVAL_WEBHOOK_SECRET` is sent as a bearer token.

A held run auto-rejects after `APPROVAL_TIMEOUT_HOURS` (default 72) if nobody pulls the lever. The audit event is `approval_expired`. The mailer is not called.

To make **Approve** the thing that actually sends, point the worker at your mailer. Reject and timeout never call it. With no URL, the worker still records `executed` and sets `delivered` to false.

```bash
python examples/mailer_sink.py
TOOL_EXECUTOR_URL=http://host.docker.internal:8092 docker compose up -d worker
```

The POST body is `event`, `tool`, and `params` (the approved To, subject, and body, including edits). Return non-2xx to fail the run. Optional `TOOL_EXECUTOR_SECRET` is sent as a bearer token. Swap the sink's print for your SMTP or Gmail call.

**From the API** (compose requires a bearer token):

```bash
TOKEN=$(curl -sS -X POST http://localhost:8081/realms/groundwire/protocol/openid-connect/token \
  -d client_id=groundwire-dashboard \
  -d grant_type=password \
  -d username=admin \
  -d password=admin | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 1. Register an agent — name, allowed tools, approval policy
curl -sS -X POST http://localhost:8000/v1/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "demo-ops-agent",
    "allowed_tools": ["send_email"],
    "approval_policy": {"require_approval_for": ["send_email"]}
  }'

# 2. Start a run (use the agent_id from step 1)
curl -sS -X POST http://localhost:8000/v1/runs \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "agent_id": "<AGENT_ID>",
    "payload": {
      "to": "ops@example.com",
      "subject": "Outage",
      "body": "Please page on-call."
    }
  }'

# 3. The run plans, then durably pauses before send_email. Decide:
curl -sS -X POST http://localhost:8000/v1/runs/<RUN_ID>/approvals \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"decision": "approve"}'
```

Endpoints also support `reject` and **edit-and-approve** (modify parameters before allowing execution), and the OpenAPI docs are at [`/docs`](http://localhost:8000/docs).

### Bring your own framework

LangChain and CrewAI examples live in [`examples/`](examples/README.md). They plan the email, then hand off to `GroundwireClient` so the send still sits at danger in the box:

```bash
pip install -e .
GROUNDWIRE_API_URL=http://localhost:18000 \
GROUNDWIRE_USERNAME=admin GROUNDWIRE_PASSWORD=admin \
python examples/langchain/ops_email.py --incident "api latency"
```

## Architecture

```
┌──────────────────┐          ┌─────────────────────┐
│  Angular          │          │  Your agent code     │
│  "signal box"     │  REST    │  (any framework:     │
│  dashboard  :4200 ├─────────►│  LangChain / CrewAI /│
└────────┬─────────┘          │  custom)             │
         │                    └──────────┬───────────┘
         ▼                               │
┌────────────────────────────────────────▼───────────┐
│          FastAPI control plane :8000                │
│  agents · runs · graph · approve · audit · OIDC     │
└───────┬───────────────────────────────┬────────────┘
        ▼                               ▼
┌───────────────────┐         ┌──────────────────────┐
│  Temporal  :7233   │         │  PostgreSQL + Keycloak │
│  AgentRunWorkflow —│         │  agents · policies ·   │
│  plan → route →    │         │  audit · OIDC :8081    │
│  approve → tool    │         └──────────────────────┘
└───────┬───────────┘
        ▼
┌───────────────────┐         Temporal UI :8088
│  Go router :8090   │
│  small vs large    │
└───────────────────┘
```

**Why these tools, concretely:**

| Component | Why *this* one |
|---|---|
| **Temporal** | Purpose-built for long-running, crash-safe, signal-resumable workflows — exactly the approval-gate pattern, without a cron+queue hack |
| **FastAPI** | Async-native, auto-generated OpenAPI docs, pydantic schemas straight from the Temporal payloads |
| **PostgreSQL** | Temporal requires a real relational store; Postgres doubles as the source of truth for agents, runs, policies, and audit records |
| **Keycloak** | Self-hostable OIDC issuer; demo realm ships with admin and operator users |
| **Angular 19 + D3** | Structured framework for a long-lived ops tool; D3 because rendering a live execution DAG is literally what it's for |
| **Go model-router** | Stdlib-only sidecar: pick a model, log cost, stay off the Python worker hot path |
| **Docker Compose** | The same file is the dev environment *and* the single-VM deployment — no hidden setup |

## Inside the signal box

The operator surface is designed as a **railway signal box** — a dim instrument panel where an approval is a brass lever on a red signal, not a modal. (Full design rationale in [`DESIGN.md`](DESIGN.md).)

- **Route strip** — every run as a row with a spectacle lamp: amber = executing, red = awaiting approval, green = completed. Filters: All routes / Live / Held (the approval inbox).
- **Interlocking diagram** — a D3-rendered DAG of the run's steps, live as it executes.
- **Levers** — Approve / Reject on the held node itself, with full context of what the agent wants to do and what it would touch.
- **Occurrence book** — Register filter: tenant-scoped audit query, JSON/CSV export, and a per-route timeline under the diagram.

## Repository layout

```
groundwire/
├── src/groundwire/
│   ├── api.py            # FastAPI control plane
│   ├── worker.py         # Temporal worker entrypoint
│   ├── models.py         # SQLAlchemy: agents, runs, approvals, audit
│   ├── services/         # agents · runs · approvals · graph
│   └── temporal/         # AgentRunWorkflow, activities, payloads
├── dashboard/            # Angular "signal box" + nginx-served build
├── router/               # Go model-router (POST /v1/route)
├── examples/             # LangChain + CrewAI → GroundwireClient
├── site/                 # navy marketing page (compose :4300)
├── tests/                # pytest: registration, runs, approvals, crash-recovery, routing, client
├── docker-compose.yml    # postgres + keycloak + temporal + router + api + worker + dashboard + site
├── CONTRIBUTING.md
├── docs/architecture.md
├── deploy/               # Keycloak realm import + Postgres init (off-root `.data/`)
├── Groundwire_PRD.md     # full product spec
├── DESIGN.md             # operator-surface design system
└── PRODUCT.md            # positioning & product principles
```

## Local development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -v                          # backend tests

cd dashboard
npm install
npm start                          # dev server on :4200, proxies /v1 → :8000
```

## Roadmap

| Milestone | Scope | Status |
|---|---|---|
| **v0.1 — Durable core** | FastAPI + Temporal + Postgres; runs survive worker crashes; gates pause/resume durably | ✅ shipped |
| **v0.2 — Visibility** | Angular signal box: run list, D3 DAG, approval inbox | ✅ shipped |
| **v0.3 — Governance** | Keycloak + OIDC, multi-tenant policies, full audit query UI | ✅ shipped |
| **v0.4 — Routing & polish** | Go model-router, Instruments gauges (incl. cost / run), first public docs pass | ✅ shipped |
| **v1.0 — Public launch** | LangChain + CrewAI example agents, hardened docs, contribution guide | ✅ shipped |

## Who this is for

- **AI/ML engineers** who need agent workflows that don't silently die, plus "ask a human first" without building it from scratch
- **Platform engineers** giving multiple teams one shared, governed way to run agents
- **Compliance-sensitive teams** that need an audit trail before agents touch production

**Deliberate non-goals (v1):** no LLM/prompting abstraction (bring your own framework), no no-code visual builder, no multi-region HA. License clarity: every dependency is free for commercial OSS use — no Highcharts.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Issues are the discussion channel; keep the operator surface a signal box (`DESIGN.md`), and keep Docker/data off `/`.

## License

[Apache 2.0](LICENSE) — chosen for the patent grant and enterprise-friendliness that match Groundwire's compliance-first positioning.

---

<div align="center">

**Full spec:** [`Groundwire_PRD.md`](Groundwire_PRD.md) · **Design:** [`DESIGN.md`](DESIGN.md) · **Product:** [`PRODUCT.md`](PRODUCT.md) · **Contribute:** [`CONTRIBUTING.md`](CONTRIBUTING.md)

*Built by [Taksha Thosani](https://github.com/taksha17)*

</div>
