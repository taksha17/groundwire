# Architecture

Groundwire is the control plane under your agent framework. LangChain, CrewAI, or a plain function plans the work. Groundwire makes the run survive a crash, stop for a human, and leave a paper trail.

```
Your agent (LangChain / CrewAI / custom)
        │  GroundwireClient: register, start_run
        ▼
FastAPI :8000  — agents, runs, approvals, audit, metrics, OIDC
        │
        ├─ PostgreSQL     contracts, run state, audit
        ├─ Keycloak       who pulled the lever
        ├─ Temporal       AgentRunWorkflow (plan → route → approve → tool)
        └─ Go router      groundwire-small vs groundwire-large + estimated cost

Angular signal box :4200  — lamps, DAG, levers, occurrence book, instruments
Public page        :4300  — same navy world; CTA opens the live box
```

The worker's demo planner is still a deterministic `send_email` plan. Example agents therefore **draft the payload in-process**, then start a Groundwire run whose gated tool is `send_email`. That is the v1 contract: you bring the framework, Groundwire brings the pause. After approve, the worker POSTs the approved params to `TOOL_EXECUTOR_URL` when that is set. A timeout on the run rejects it without calling the mailer.
