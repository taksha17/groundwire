<div align="center">

# Groundwire

### Durable, governed infrastructure for AI agents

**Your agent framework decides *what* to do. Groundwire guarantees it actually happens — safely, durably, and with a paper trail.**

[![Status](https://img.shields.io/badge/status-v0.1%20in%20development-orange)]()
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Self-hostable](https://img.shields.io/badge/cost%20to%20self--host-%240-success)]()
[![Framework](https://img.shields.io/badge/works%20with-LangChain%20%C2%B7%20LangGraph%20%C2%B7%20CrewAI%20%C2%B7%20custom-purple)]()

</div>

---

## The problem

AI agents are great in demos and fragile in production. If you've tried to run an agent against real operational systems, you've hit this wall:

- **💥 Long-running agents die silently.** A task that calls five tools and waits on a human can take minutes to hours. One process restart, and most frameworks lose everything and start over.
- **🙋 "Human-in-the-loop" is bolted on.** An `input()` call or a fire-and-forget webhook isn't an approval gate. What happens when your approver doesn't respond for three days?
- **📜 There's no real audit trail.** When an agent sends an email, modifies a record, or calls a paid API — can you answer *who authorized this, under what policy, and why the agent decided to do it*? In any regulated context, "we don't know" is a showstopper.
- **🔑 Identity is an afterthought.** Most frameworks don't integrate with enterprise SSO, so "which human is accountable for this agent's actions?" is often unanswerable.

Existing tools each solve a slice. **LangGraph / CrewAI** are great at agent *logic*, weak on durability and governance. **Temporal / Windmill / n8n** are great at durable workflows, but aren't built around agent primitives. **Nobody combines them — purpose-built for agents.** That's Groundwire.

## What Groundwire is

Groundwire is an open-source **control plane** that sits *underneath* your agent framework (LangChain, LangGraph, CrewAI, or plain Python functions) as the execution and governance layer.

**You keep your agent logic. Groundwire guarantees it runs reliably, safely, and audibly.**

| Capability | What it means |
|---|---|
| ⏳ **Durable execution** | Every run is a Temporal workflow. Crash mid-run, restart, redeploy — the run resumes exactly where it left off. Zero state loss. |
| ✋ **First-class approval gates** | Flag any step as requiring human approval. The workflow durably pauses — for minutes or *weeks* — until someone approves, rejects, or **edits-and-approves**. |
| 📖 **Complete audit trail** | Every plan, tool call, approval decision, and identity is written as an immutable, timestamped, queryable audit record. Export as CSV/JSON. |
| 🔐 **Enterprise identity** | OIDC SSO out of the box via Keycloak, federating to Azure AD, Okta, and Google Workspace. Role-based policies, scoped per tenant. |
| 🧩 **Framework-agnostic** | Groundwire stores the contract (name, allowed tools, approval policy); your code holds the logic. No lock-in, no new agent DSL. |
| 💸 **$0 to self-host** | `docker compose up` locally, or Oracle Cloud Free Tier + Cloudflare Pages/Workers for a live deployment. Enterprise-grade governance at hobbyist prices. |

## Quick start

```bash
git clone https://github.com/taksha17/groundwire.git
cd groundwire
docker compose up
```

That's it — one command brings up the **entire stateful backend**: Temporal, PostgreSQL, Keycloak, the FastAPI control plane, and the Go model router. Target: `git clone` → working dashboard with a demo agent in **under 10 minutes**.

Then register an agent and trigger a run:

```python
from groundwire import GroundwireClient

gw = GroundwireClient("http://localhost:8000")

gw.register_agent(
    name="invoice-processor",
    allowed_tools=["read_invoice", "update_ledger", "send_email"],
    approval_policy={"send_email": "requires_approval"},  # human gates this tool
)

run = gw.start_run("invoice-processor", input={"invoice_id": "INV-2041"})
# The agent plans and works autonomously — until it tries to send an email.
# The run durably pauses. An approver reviews the exact action in the dashboard,
# edits the draft if needed, and approves. The run resumes. Everything is logged.
```

## Architecture

```
┌─────────────────┐      ┌──────────────────────┐
│  Angular         │      │  Your agent code      │
│  Dashboard       │      │  (LangChain /         │
│  (Cloudflare     │      │   LangGraph / CrewAI /│
│   Pages)         │      │   custom)             │
└────────┬─────────┘      └──────────┬────────────┘
         │  OIDC (Keycloak)          │ Groundwire SDK
         ▼                           ▼
┌──────────────────────────────────────────────────┐
│           FastAPI Control Plane API               │
│  agent registry · run triggers · approvals ·      │
│  audit query · policy evaluation                  │
└───────┬─────────────────────┬────────────────────┘
        │                     │
        ▼                     ▼
┌───────────────┐     ┌──────────────────┐
│   Temporal     │     │   PostgreSQL      │
│  durable       │     │  agent defs ·     │
│  workflow      │     │  policies ·       │
│  execution     │     │  audit log        │
└───────┬────────┘     └──────────────────┘
        │
        ▼
┌───────────────────────┐
│  Go Model Router       │
│  (right-size the model │
│   per task, log why)   │
└───────────────────────┘
```

**Why these tools, concretely:**

| Component | Why *this* one |
|---|---|
| **Temporal** | Purpose-built for long-running, crash-safe, signal-resumable workflows — exactly the approval-gate pattern, without a cron+queue hack |
| **FastAPI** | Async-native, auto-generated OpenAPI docs, pairs naturally with the Temporal Python SDK worker |
| **Keycloak** | Self-hostable OIDC issuer that federates to Azure AD / Okta / Google — enterprise SSO with zero per-provider integration code |
| **Angular** | Opinionated structure suits a long-lived admin dashboard with many views (runs, approvals, policies, audit) |
| **D3.js** | Live execution DAG rendering for runs — this is what D3 is *for* |
| **PostgreSQL** | Temporal requires a real relational store; Postgres is the standard, well-supported choice |
| **Go model router** | Small, fast, concurrent routing service; routes each LLM call to the right-sized model and logs the decision |
| **Cloudflare Pages/Workers/Queues** | Genuinely free for the stateless/edge pieces (frontend hosting, auth proxy, live-update event bus); Redpanda/Kafka as a fully self-hosted fallback |

> **License clarity by design:** every dependency is free for commercial OSS use. Charts use Chart.js / Apache ECharts (MIT/Apache) — Highcharts is deliberately excluded.

## The dashboard

One Angular app, four jobs:

- **📋 Live run list** — every run, filterable by status (`planning`, `awaiting_approval`, `executing`, `completed`, `failed`, `rejected`)
- **🕸️ Execution DAG** — D3-rendered, live-updating graph of any in-progress or completed run
- **✉️ Approval inbox** — pending gates with full context: *what* the agent wants to do, *why*, and *what data it touches*. Approve, reject, or edit-and-approve.
- **📈 Metrics** — success rate, average duration, approval turnaround, cost-per-run

## Core concepts

| Concept | Definition |
|---|---|
| **Agent Definition** | Registered contract: name, allowed tools, approval policy. Versioned — every run records which version it executed under. |
| **Run** | One durable execution of an Agent Definition, modeled as a Temporal workflow. |
| **Step** | A model call, tool call, or approval gate inside a Run — individually retried without re-running the whole Run. |
| **Approval Gate** | A Step that durably pauses the Run on a Temporal signal until a human decides. The pause can last indefinitely. |
| **Policy** | Rules for which tools need approval and who can approve them — scoped per tenant. |
| **Tenant** | An isolated workspace; all data, policies, and identities are tenant-scoped. |
| **Audit Record** | Immutable, timestamped log of every step transition, decision, and the identity responsible. |

## Roadmap

| Milestone | Scope |
|---|---|
| ✅ **v0.1 — Durable core** | FastAPI + Temporal + Postgres. Prove a run survives a worker crash and an approval gate durably pauses/resumes. |
| 🔜 **v0.2 — Visibility** | Angular dashboard: run list, run detail, D3 DAG viewer, approval inbox. |
| **v0.3 — Governance** | Keycloak + OIDC, multi-tenant policies, full audit log + query UI. |
| **v0.4 — Routing & polish** | Go model router, metrics dashboard, `docker compose up` one-liner, public docs. |
| **v1.0 — Public launch** | Example agents (LangChain + CrewAI), hardened docs, contribution guide. |

## Who this is for

- **AI/ML engineers** who need agent workflows that don't silently die, plus "ask a human first" without building it from scratch
- **Platform engineers** giving multiple teams one shared, governed way to run agents
- **Compliance-sensitive teams** (fintech, healthcare-adjacent, enterprise consulting) that need an audit trail before agents touch production

## Non-goals (v1)

To stay focused, Groundwire deliberately does **not**:

- ❌ Provide its own LLM/prompting abstraction — bring your own framework
- ❌ Become a no-code visual builder (unlike n8n) — it's a developer-first SDK + control plane
- ❌ Do multi-region/HA — single-region self-hosted is the v1 target

## Contributing

Groundwire is in early active development. Contributions, design feedback, and "have you thought about…" issues are all welcome — the roadmap above shows where help lands best. A full contribution guide ships with v1.0.

## License

Apache 2.0 (proposed) — chosen for the patent grant and enterprise-friendliness that match Groundwire's compliance-first positioning.

---

<div align="center">

**Full design details:** see [`Groundwire_PRD.md`](Groundwire_PRD.md)

*Built by [Taksha Thosani](https://github.com/taksha17)*

</div>
