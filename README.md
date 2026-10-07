<div align="center">

# Groundwire

### Durable, governed infrastructure for AI agents

**The pause is the product.** Your agent framework decides *what* to do — Groundwire guarantees it survives crashes, stops for a human when it matters, and leaves a paper trail.

[![Status](https://img.shields.io/badge/release-v0.2%20%E2%80%94%20Visibility-orange)](Groundwire_PRD.md)
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
| 📖 **Audit records** | ✅ shipped | Every run, step, and approval decision is persisted and queryable. Full audit query UI ships in v0.3. |
| 🔐 **Enterprise identity** | 🔜 v0.3 | OIDC SSO via Keycloak, federating to Azure AD / Okta / Google. |
| 🧠 **Model routing** | 🔜 v0.4 | Go service routing each LLM call to the right-sized model, with logged decisions. |

## Quick start

```bash
git clone https://github.com/taksha17/groundwire.git
cd groundwire
docker compose up --build
```

One command brings up the whole stateful backend — **Postgres, Temporal (+ UI), the FastAPI control plane, the durable worker, and the dashboard**. First boot takes a minute while Temporal auto-setup runs.

| Surface | URL |
|---|---|
| 🖥️ Dashboard (signal box) | http://localhost:4200 |
| 🔌 Control plane API | http://localhost:8000 |
| 🔭 Temporal UI | http://localhost:8088 |

Ports taken? `GROUNDWIRE_API_PORT=18000 GROUNDWIRE_DASHBOARD_PORT=4201 docker compose up --build`

### Try it: a gated agent in 60 seconds

**From the dashboard** — open the signal box, click **Set a route**. That registers the demo agent and starts a `send_email` run. When the lamp goes red (`awaiting_approval`), pull **Approve** or **Reject** directly on the DAG node. Now for the fun part: `docker compose restart worker` while it's held — the run is still there, waiting. *That's the point.*

**From the API:**

```bash
# 1. Register an agent — name, allowed tools, approval policy
curl -sS -X POST http://localhost:8000/v1/agents \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "demo-ops-agent",
    "allowed_tools": ["send_email"],
    "approval_policy": {"require_approval_for": ["send_email"]}
  }'

# 2. Start a run (use the agent_id from step 1)
curl -sS -X POST http://localhost:8000/v1/runs \
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
  -H 'Content-Type: application/json' \
  -d '{"decision": "approve", "actor": "you"}'
```

Endpoints also support `reject` and **edit-and-approve** (modify parameters before allowing execution), and the OpenAPI docs are at [`/docs`](http://localhost:8000/docs).

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
│  agents · runs · graph · approve / reject / edit    │
└───────┬───────────────────────────────┬────────────┘
        ▼                               ▼
┌───────────────────┐         ┌──────────────────────┐
│  Temporal  :7233   │         │  PostgreSQL           │
│  AgentRunWorkflow —│         │  agent defs · runs ·  │
│  durable steps +   │         │  approval decisions · │
│  signal-backed     │         │  audit records        │
│  approval gates    │         └──────────────────────┘
└───────┬───────────┘
        ▼
   Temporal UI :8088 (workflow history inspector)
```

**Why these tools, concretely:**

| Component | Why *this* one |
|---|---|
| **Temporal** | Purpose-built for long-running, crash-safe, signal-resumable workflows — exactly the approval-gate pattern, without a cron+queue hack |
| **FastAPI** | Async-native, auto-generated OpenAPI docs, pydantic schemas straight from the Temporal payloads |
| **PostgreSQL** | Temporal requires a real relational store; Postgres doubles as the source of truth for agents, runs, and audit records |
| **Angular 19 + D3** | Structured framework for a long-lived ops tool; D3 because rendering a live execution DAG is literally what it's for |
| **Docker Compose** | The same file is the dev environment *and* the single-VM deployment — no hidden setup |

## Inside the signal box

The operator surface is designed as a **railway signal box** — a dim instrument panel where an approval is a brass lever on a red signal, not a modal. (Full design rationale in [`DESIGN.md`](DESIGN.md).)

- **Route strip** — every run as a row with a spectacle lamp: amber = executing, red = awaiting approval, green = completed. Filters: All routes / Live / Held (the approval inbox).
- **Interlocking diagram** — a D3-rendered DAG of the run's steps, live as it executes.
- **Levers** — Approve / Reject on the held node itself, with full context of what the agent wants to do and what it would touch.

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
├── tests/                # pytest: registration, runs, approvals, crash-recovery
├── docker-compose.yml    # postgres + temporal + temporal-ui + api + worker + dashboard
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
| **v0.3 — Governance** | Keycloak + OIDC, multi-tenant policies, full audit query UI | planned |
| **v0.4 — Routing & polish** | Go model-router, metrics (Chart.js/ECharts), first public docs pass | planned |
| **v1.0 — Public launch** | LangChain + CrewAI example agents, hardened docs, contribution guide | planned |

## Who this is for

- **AI/ML engineers** who need agent workflows that don't silently die, plus "ask a human first" without building it from scratch
- **Platform engineers** giving multiple teams one shared, governed way to run agents
- **Compliance-sensitive teams** that need an audit trail before agents touch production

**Deliberate non-goals (v1):** no LLM/prompting abstraction (bring your own framework), no no-code visual builder, no multi-region HA. License clarity: every dependency is free for commercial OSS use — no Highcharts.

## Contributing

Early days — design feedback, issues, and "have you thought about…" are all welcome. The roadmap shows where help lands best; a full contribution guide ships with v1.0.

## License

[Apache 2.0](LICENSE) — chosen for the patent grant and enterprise-friendliness that match Groundwire's compliance-first positioning.

---

<div align="center">

**Full spec:** [`Groundwire_PRD.md`](Groundwire_PRD.md) · **Design:** [`DESIGN.md`](DESIGN.md) · **Product:** [`PRODUCT.md`](PRODUCT.md)

*Built by [Taksha Thosani](https://github.com/taksha17)*

</div>
