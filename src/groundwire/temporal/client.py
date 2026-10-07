import asyncio
from uuid import UUID

from temporalio.client import Client

from groundwire.settings import Settings
from groundwire.temporal.payloads import ApprovalDecision, RunWorkflowInput
from groundwire.temporal.workflows import AgentRunWorkflow


class TemporalClient:
    def __init__(self, client: Client, task_queue: str) -> None:
        self._client = client
        self._task_queue = task_queue

    async def start_run_workflow(self, input: RunWorkflowInput) -> None:
        await self._client.start_workflow(
            AgentRunWorkflow.run,
            input,
            id=f"run-{input.run_id}",
            task_queue=self._task_queue,
        )

    async def signal_approval(self, run_id: UUID, decision: ApprovalDecision) -> None:
        handle = self._client.get_workflow_handle(f"run-{run_id}")
        await handle.signal(AgentRunWorkflow.approval_decision, decision)


async def connect_temporal_sdk(settings: Settings, attempts: int = 60) -> Client:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return await Client.connect(
                settings.temporal_address, namespace=settings.temporal_namespace
            )
        except Exception as exc:  # Temporal is not ready during compose startup
            last_error = exc
            await asyncio.sleep(1)
    raise RuntimeError(
        f"could not connect to Temporal at {settings.temporal_address}"
    ) from last_error


async def connect_temporal(settings: Settings) -> TemporalClient:
    client = await connect_temporal_sdk(settings)
    return TemporalClient(client, settings.temporal_task_queue)
