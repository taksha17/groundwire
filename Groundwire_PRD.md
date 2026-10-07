# Groundwire — Product Requirements Document

**Durable, governed infrastructure for AI agents**

| | |
|---|---|
| Status | Draft v0.1 |
| Owner | Taksha Thosani |
| Last updated | October 2026 |
| License (proposed) | Apache 2.0 |

---

## 1. Summary

Groundwire is an open-source control plane for running AI agent workflows that are **durable** (survive crashes and restarts without losing state), **governed** (every consequential action can require human approval and is tied to an authenticated identity), and **auditable** (every decision an agent makes is logged and explainable after the fact).

It sits underneath agent frameworks (LangChain, LangGraph, CrewAI, custom agents) as the execution and governance layer, rather than competing with them as "yet another agent framework." You keep your agent logic; Groundwire guarantees it runs reliably, safely, and with a paper trail.

---

## 2. Problem Statement

Teams building AI agents for real operational work (not demos) run into the same wall within a few weeks:

1. **Agents are long-running and crash-prone.** A multi-step agent task that calls five tools and waits on a human approval can take minutes to hours. If the process restarts, most frameworks lose all progress and start over.
2. **"Human-in-the-loop" is usually bolted on.** Most agent frameworks treat approval gates as an afterthought — a `input()` call or a webhook with no durability guarantee if the approver doesn't respond for three days.
3. **There's no real audit trail.** When an autonomous agent takes an action (sends an email, modifies a record, calls a paid API), most teams can't answer "who authorized this, under what policy, and why did the agent decide to do it" after the fact — which blocks adoption in any regulated or enterprise context.
4. **Identity is an afterthought.** Agent frameworks rarely integrate with real enterprise SSO (Okta, Azure AD, Keycloak), so "which human is accountable for this agent's actions" is often unanswerable.

Existing tools each solve a slice of this:
- **LangGraph / CrewAI** — good at agent *logic*, weak on durability and governance.
- **Temporal / Windmill / n8n** — good at durable workflow execution, but not built around agent-specific primitives (tool calls, model routing, approval-as-a-first-class-step).
- **n8n, Windmill** — visual automation, but not designed for the LLM-agent-with-reasoning-loop pattern specifically, and governance/SSO is shallow.

No OSS project currently combines durable execution + first-class human approval + enterprise identity + audit trail, purpose-built for agents. That's the gap Groundwire fills.

---

## 3. Goals

- **G1.** An agent workflow (plan → tool calls → optional human approval → execute → record) survives a full process crash/restart with zero state loss.
- **G2.** Any step in an agent's workflow can be marked as requiring human approval, with the workflow durably paused until a decision is made — minutes or weeks later, it doesn't matter.
- **G3.** Every agent run produces a complete, queryable audit log: what was planned, what tools were called, what a human approved/rejected, and why.
- **G4.** Enterprise-grade identity out of the box: SSO via OIDC, with Keycloak as the reference identity provider, federating to Azure AD, Okta, Google Workspace, etc.
- **G5.** Framework-agnostic: works with agents built in LangChain, LangGraph, CrewAI, or plain function calls — Groundwire doesn't dictate how you write agent logic.
- **G6.** Self-hostable end-to-end for $0 using only free-tier/OSS infrastructure (Docker Compose locally; Fly.io or Oracle Cloud Free Tier for a live deployment).
- **G7.** A genuinely good first-run experience: `docker compose up` to a working dashboard with a demo agent in under 10 minutes.

### Non-Goals (v1)

- Groundwire does **not** provide its own LLM-calling/prompting abstraction — bring your own agent framework.
- Groundwire does **not** attempt to be a no-code visual builder (contrast with n8n) — it's a developer-first SDK + control plane.
- Multi-region/HA deployment topology is out of scope for v1; single-region self-hosted is the target.

---

## 4. Target Users

| Persona | Need |
|---|---|
| **AI/ML engineer at a startup or consultancy** (e.g., building agent automations for internal tools or client engagements) | Needs agent workflows that don't silently die, and a cheap way to add "ask a human first" without building it from scratch |
| **Platform/infra engineer at a mid-size company** | Needs to give multiple teams a shared, governed way to run agents without each team reinventing durability and auth |
| **Compliance-sensitive teams (fintech, healthcare-adjacent, enterprise consulting)** | Needs an audit trail and identity-tied accountability before agents are allowed to touch production systems |

---

## 5. Core Concepts

- **Agent Definition** — a registered unit describing an agent's name, the tools it may call, and its approval policy. Logic lives in your code; Groundwire stores the contract.
- **Run** — one durable execution of an Agent Definition, modeled as a Temporal workflow. Has a status (`planning`, `awaiting_approval`, `executing`, `completed`, `failed`, `rejected`).
- **Step** — one unit inside a Run: a model call, a tool call, or an approval gate. Steps are individually retried on failure without re-running the whole Run.
- **Approval Gate** — a Step that pauses the Run and notifies a human (via dashboard, email, or webhook) until they approve, reject, or edit-and-approve the pending action. Backed by a Temporal signal, so the pause can last indefinitely.
- **Policy** — a rule set (which tools require approval, which users/roles can approve for which agents) scoped per tenant.
- **Tenant** — an isolated organization/workspace; all data, policies, and identities are tenant-scoped.
- **Audit Record** — an immutable, timestamped entry logging every Step transition, decision, and the identity responsible for it.

---

## 6. System Architecture

```
┌─────────────────┐      ┌──────────────────────┐
│  Angular         │      │  Agent code           │
│  Dashboard       │      │  (your framework:      │
│  (Cloudflare     │      │  LangChain/LangGraph/  │
│   Pages)         │      │  CrewAI/custom)        │
└────────┬─────────┘      └──────────┬─────────────┘
         │  OIDC (Keycloak)          │ Groundwire SDK
         ▼                            ▼
┌─────────────────────────────────────────────────┐
│          FastAPI Control Plane API               │
│   (agent registry, run triggers, approvals,       │
│    audit query, policy evaluation)                │
└───────┬─────────────────────┬─────────────────────┘
        │                     │
        ▼                     ▼
┌───────────────┐     ┌──────────────────┐
│  Temporal      │     │  PostgreSQL       │
│  (durable       │     │  (agent defs,     │
│   workflow      │     │   policies,       │
│   execution)    │     │   audit log)      │
└───────┬────────┘     └──────────────────┘
        │
        ▼
┌───────────────────────┐
│  Go Model-Router        │
│  Service (extends        │
│  Lumen Stream Lab logic) │
└───────────────────────┘

Event bus for live dashboard updates: Cloudflare Queues (hosted) or Redpanda/Kafka (self-hosted)
```

**Why each piece, concretely:**

| Component | Role | Why this tool specifically |
|---|---|---|
| Temporal | Executes each Run as a durable workflow | Purpose-built for exactly this: long-running, crash-safe, signal-resumable workflows |
| FastAPI | Public API (register agents, trigger runs, approve/reject, query audit log) | Async-native, auto-generated OpenAPI docs, pairs naturally with a Temporal Python SDK worker |
| Keycloak | Identity provider, OIDC issuer | Self-hostable, federates to Azure AD/Okta/Google — gives enterprise SSO without per-provider integration code |
| Angular | Admin/ops dashboard | Structured, opinionated framework suits a long-lived internal-tool-style dashboard with many views (runs, approvals, policies, audit) |
| D3.js | Live execution DAG viewer for a Run | Purpose-built graph rendering — this is what D3 is for, not a generic chart library |
| PostgreSQL | Source of truth for agent defs, policies, audit log; Temporal's persistence store | Temporal requires a real relational store; Postgres is the standard, well-supported choice |
| Go model-router service | Routes LLM calls to the right-sized model based on task complexity | Extends the author's existing Lumen Stream Lab project; Go suits a small, fast, concurrent routing service |
| Cloudflare Pages/Workers/Queues | Frontend hosting, lightweight edge logic, event bus | Genuinely free, and the right shape for stateless/edge-triggered pieces (see §9 on hosting) |

---

## 7. Functional Requirements

### 7.1 Agent Registration
- FR1: Developers register an Agent Definition via SDK call or API (`name`, `allowed_tools[]`, `approval_policy`).
- FR2: Agent Definitions are versioned; a Run always records which version it executed under.

### 7.2 Durable Run Execution
- FR3: Starting a Run creates a Temporal workflow instance; the Run survives worker restarts, deploys, and crashes.
- FR4: Each Step (model call, tool call) is individually retried per a configurable retry policy before failing the Run.
- FR5: Run state (current step, history, intermediate outputs) is queryable in real time via API and dashboard.

### 7.3 Human Approval Gates
- FR6: Any Step can be flagged as requiring approval; the workflow durably pauses via a Temporal signal wait.
- FR7: Pending approvals are visible on the dashboard with full context (what the agent wants to do, why, what data it would touch).
- FR8: Approvers can approve, reject, or edit-and-approve (modify parameters before allowing execution).
- FR9: Approval timeouts are configurable (e.g., auto-escalate or auto-reject after N hours).

### 7.4 Identity & Access
- FR10: All dashboard and API access is authenticated via OIDC against Keycloak.
- FR11: Role-based policy: who can register agents, who can approve for which agent/tool combinations, scoped per tenant.
- FR12: Every Audit Record is tied to an authenticated identity (human or service account).

### 7.5 Audit Log
- FR13: Every Step transition, approval decision, and Run outcome is written as an immutable Audit Record.
- FR14: Audit Records are queryable by agent, tenant, date range, and outcome; exportable as CSV/JSON.
- FR15: An audit view reconstructs a full Run timeline for post-hoc review.

### 7.6 Model Routing
- FR16: The Go router service exposes an endpoint that, given a task/prompt profile, returns the recommended model and routes the call, logging the routing decision.

### 7.7 Dashboard
- FR17: Live Run list with status filters.
- FR18: D3-rendered execution DAG for an in-progress or completed Run.
- FR19: Approval inbox.
- FR20: Metrics view: run success rate, average duration, approval turnaround time, cost-per-run (via Chart.js/ECharts — not Highcharts, license reasons).

---

## 8. Non-Functional Requirements

- **Self-hostable for $0** using Docker Compose (local) or a single free-tier VM (Oracle Cloud Free Tier / Fly.io) for the stateful backend, plus Cloudflare Pages/Workers for the frontend/edge pieces.
- **Setup time** from clone to working demo agent under 10 minutes.
- **Horizontal scalability** of Temporal workers (not required for v1, but the architecture shouldn't block it later).
- **License clarity**: every dependency chosen must be free for commercial OSS use (this is why Highcharts is explicitly excluded in favor of Chart.js/Apache ECharts, both MIT).

---

## 9. Hosting & Deployment Plan

| Layer | Where | Why |
|---|---|---|
| Angular dashboard (static build) | Cloudflare Pages | Free, fast, right tool for a static SPA |
| Edge logic (auth proxy, webhooks) | Cloudflare Workers | Free tier (100k req/day) covers this easily |
| Event bus (live dashboard updates) | Cloudflare Queues, or Redpanda if fully self-hosted | Free tier viable; Redpanda as a no-cloud-dependency fallback |
| Temporal server, Keycloak, Postgres, FastAPI, Go router | Single VM via Docker Compose — **Oracle Cloud Free Tier** (always-free, no trial expiry) or **Fly.io** free allowance | These are stateful, always-on services; Cloudflare Containers' ephemeral model is a poor fit for this today — confirmed by checking current docs rather than assuming |

A single `docker-compose.yml` should bring up the entire stateful backend locally for development, with the same compose file deployable to the VM for a live demo.

---

## 10. Milestones

| Milestone | Scope |
|---|---|
| **v0.1 — Durable core** | FastAPI + Temporal + Postgres. One agent type, no auth yet. Prove: a Run survives a worker crash, and an approval gate durably pauses/resumes. |
| **v0.2 — Visibility** | Angular dashboard: run list, run detail, D3 DAG viewer, approval inbox (basic approve/reject). |
| **v0.3 — Governance** | Keycloak + OIDC in front of the API and dashboard. Multi-tenant policy model. Full audit log + query UI. |
| **v0.4 — Routing & polish** | Go model-router service integrated. Metrics dashboard (Chart.js/ECharts). Docker Compose one-liner setup. First public README/docs pass. |
| **v1.0 — Public launch** | Hardened docs, example agents (one LangChain example, one CrewAI example), contribution guide, Discord/discussions enabled. |

---

## 11. Success Metrics (post-launch)

- GitHub stars / forks as an adoption proxy (directional, not the goal itself).
- Time from `git clone` to first successful Run in the quick-start guide (`target: < 10 minutes`).
- At least one non-trivial external contribution (issue, PR, or integration) within 3 months of public launch.
- Able to demo, end-to-end, in an interview setting: register an agent, trigger a run, approve a gated action, and show the audit trail — this is a concrete usability bar, not just a technical one.

---

## 12. Risks & Open Questions

| Risk | Mitigation |
|---|---|
| Temporal has a learning curve and adds operational weight | Document the "why Temporal" decision clearly; provide a one-command Docker Compose that hides most of the complexity for newcomers |
| Scope creep — this can balloon into "build a whole platform" | Hold the line at the milestone scope above; resist adding a visual workflow builder or multi-framework agent SDK in v1 |
| Chosen name/domain availability unconfirmed | Run a final GitHub org / npm / PyPI / domain check before public announcement |
| Cloudflare free-tier terms have changed multiple times in 2026 | Treat Cloudflare usage as the stateless/edge layer only; don't depend on free-tier terms for the stateful backend, which lives on the VM regardless |

**Open questions to resolve before v0.1 starts:**
1. Python or Go for the Temporal worker that runs agent logic? (Python likely wins for ecosystem fit with LangChain/CrewAI.)
2. Should approval notifications support Slack/email out of the box in v0.2, or stay dashboard-only until v0.3?
3. License: Apache 2.0 (patent grant, enterprise-friendly) vs. MIT (simpler) — leaning Apache 2.0 given the enterprise/compliance positioning.

---

## 13. Why This Is a Strong Portfolio/OSS Project

- It demonstrates genuine architectural decision-making (why Temporal over a cron+queue hack, why Keycloak over rolling custom auth) rather than a checklist of technologies bolted together.
- It fills a real, citable gap — no current OSS project combines durable execution + first-class approval gates + enterprise identity for agents specifically.
- It's incrementally demoable at every milestone (v0.1 alone is a legitimate "look what I built" story), so it doesn't require finishing the whole thing to be worth showing.
