# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Angular dashboard (PRD-pinned) talking to the FastAPI control plane. D3.js renders a run’s execution DAG. Keycloak OIDC on API and dashboard. Docker Compose self-host.

## Users

Primary: an AI/ML engineer running their own agents. They watch live runs, open one run, and approve or reject a gated tool call.

Also served: platform/infra engineers on a shared control plane; compliance reviewers reading the occurrence book.

## Product Purpose

Groundwire is the durable execution and governance layer under agent frameworks. It does not write agent logic. It guarantees a run survives crashes, can pause indefinitely for a human decision, and leaves a paper trail.

v1.0 success: the signal box behind Keycloak, a Go model-router on the run path, and example agents that keep their own framework. LangChain or CrewAI drafts the work; Groundwire holds the gated tool. Tenant-scoped data. Operator cannot register agents. Approvals are tied to the signed-in identity. Cost / run lights once a routed run exists.

## Positioning

Durable workflow execution plus first-class human approval plus an agent-shaped audit trail, without becoming another agent framework or a no-code builder.

## Operating Context

The operator keeps a live board up while agents run, and also comes in from an approval ping during an incident: decide, leave. Demo users: `admin` / `admin` and `operator` / `operator` in the imported Keycloak realm. Demo agent is a deterministic `send_email` plan.

## Capabilities and Constraints

- v1.0 surfaces: live run list; DAG with a router node; approval levers; occurrence book; analog instrument gauges including cost / run; Keycloak sign-in; Go model-router; LangChain and CrewAI examples via `GroundwireClient`; public page on compose `:4300` (CTA opens the live box). Set a route is always on the plate.
- Approval pings: optional `APPROVAL_WEBHOOK_URL` on the worker when a run hits danger. Optional `TOOL_EXECUTOR_URL` is the real send, called only after approve. Held runs auto-reject after `APPROVAL_TIMEOUT_HOURS` (default 72). Visual workflow builder is out.
- Status vocabulary is fixed: `planning`, `awaiting_approval`, `executing`, `completed`, `failed`, `rejected`.
- License Apache 2.0; no Highcharts.

## Brand Commitments

Name: Groundwire. Voice is operator-direct, not marketing. No invented customers, logos, or testimonials.

## Evidence on Hand

- `Groundwire_PRD.md` — product spec
- Working compose demo (`README.md`): API, Temporal worker, Keycloak, Go router, signal box, public page
- `DESIGN.md` — night control-plane world shared by `site/index.html` and the dashboard

## Product Principles

- The pause is the product: an approval gate is a first-class, durable state, not a modal afterthought.
- Show what the agent wants to do, why, and what it would touch, before asking for a decision.
- Framework-agnostic: the dashboard governs runs, it does not author prompts.
- Self-hostable and cheap: compose remains the first-run path.
