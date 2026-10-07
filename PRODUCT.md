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

v0.4 success: the same signal box, now behind Keycloak, with a Go model-router on the run path. Tenant-scoped data. Operator cannot register agents. Approvals are tied to the signed-in identity. The occurrence book is queryable and exportable. Cost / run is no longer dark once a routed run exists.

## Positioning

Durable workflow execution plus first-class human approval plus an agent-shaped audit trail, without becoming another agent framework or a no-code builder.

## Operating Context

The operator keeps a live board up while agents run, and also comes in from an approval ping during an incident: decide, leave. Demo users: `admin` / `admin` and `operator` / `operator` in the imported Keycloak realm. Demo agent is a deterministic `send_email` plan.

## Capabilities and Constraints

- v0.4 surfaces: live run list; DAG with a router node; approval levers; occurrence book; analog instrument gauges including cost / run; Keycloak sign-in; Go model-router. Set a route is always on the plate.
- Not yet: Slack/email notifications, visual workflow builder, LangChain/CrewAI examples.
- Status vocabulary is fixed: `planning`, `awaiting_approval`, `executing`, `completed`, `failed`, `rejected`.
- License Apache 2.0; no Highcharts.

## Brand Commitments

Name: Groundwire. Voice is operator-direct, not marketing. No invented customers, logos, or testimonials.

## Evidence on Hand

- `Groundwire_PRD.md` — product spec
- Working v0.1 API + Temporal worker + compose demo (`README.md`)
- No existing visual UI, DESIGN.md, or brand assets

## Product Principles

- The pause is the product: an approval gate is a first-class, durable state, not a modal afterthought.
- Show what the agent wants to do, why, and what it would touch, before asking for a decision.
- Framework-agnostic: the dashboard governs runs, it does not author prompts.
- Self-hostable and cheap: compose remains the first-run path.
