# Example agents

Groundwire does not write agent logic. These examples show the split:

1. **LangChain** or **CrewAI** drafts the email.
2. `GroundwireClient` registers the agent contract and starts a durable run.
3. The signal box holds `send_email` at danger until a human approves.

Both scripts default to an offline canned draft so you can run them without extra packages or API keys. Pass `--live` only when you have installed that example's `requirements.txt` and an `OPENAI_API_KEY`.

## Run against compose

```bash
pip install -e .
export GROUNDWIRE_API_URL=http://localhost:18000   # or :8000 if you did not remap the port
export GROUNDWIRE_USERNAME=admin
export GROUNDWIRE_PASSWORD=admin

python examples/langchain/ops_email.py --incident "api latency"
python examples/crewai/ops_email.py --incident "api latency"
python examples/sre_incident_storm.py --count 48
```

Each process prints a run id and the dashboard URL. Open the box, wait for the red lamp, pull **Approve**. To get a ping instead of watching the strip, run `python examples/webhook_sink.py` and set `APPROVAL_WEBHOOK_URL=http://host.docker.internal:8091` on the worker. To send from the gate itself, run `python examples/mailer_sink.py` and set `TOOL_EXECUTOR_URL=http://host.docker.internal:8092`. Reject and the 72-hour timeout never hit that process.

`GROUNDWIRE_TOKEN` can replace the username/password pair if you already have a bearer token. Do not commit tokens.

## Client

```python
from groundwire.client import client_from_env
from groundwire.handoff import canned_outage_email, ensure_ops_agent, start_gated_email

with client_from_env() as gw:
    agent = ensure_ops_agent(gw, "my-ops-email")
    run = start_gated_email(gw, agent["id"], canned_outage_email("disk full"))
    held = gw.wait_for_status(run["id"], ["awaiting_approval"])
```
