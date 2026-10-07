# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Angular dashboard (PRD-pinned) talking to the existing FastAPI control plane. D3.js renders a run’s execution DAG. Docker Compose self-host. Auth is out of scope until v0.3.

## Users

Primary: an AI/ML engineer running their own agents. They watch live runs, open one run, and approve or reject a gated tool call.

Also served, not primary for v0.2: platform/infra engineers on a shared control plane; compliance reviewers (full audit query UI is v0.3).

## Product Purpose

Groundwire is the durable execution and governance layer under agent frameworks. It does not write agent logic. It guarantees a run survives crashes, can pause indefinitely for a human decision, and leaves a paper trail.

v0.2 success: from the dashboard, an operator can see live runs, inspect a run as a DAG, and approve or reject a pending action — including after a worker restart.

## Positioning

Durable workflow execution plus first-class human approval plus an agent-shaped audit trail, without becoming another agent framework or a no-code builder.

## Operating Context

The operator keeps a live board up while agents run, and also comes in from an approval ping during an incident: decide, leave. v0.1 already proves a run can sit in `awaiting_approval` across worker restarts; the dashboard is how a human finds that pause and acts. No SSO in v0.2. Demo agent is a deterministic `send_email` plan.

## Capabilities and Constraints

- v0.2 surfaces: live run list with status filters; run detail with D3 execution DAG; approval inbox with approve/reject (edit-and-approve exists in the API).
- Not in v0.2: Keycloak/OIDC, metrics charts, Go model-router, Slack/email notifications, visual workflow builder.
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
