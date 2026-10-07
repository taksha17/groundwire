from typing import Protocol
from uuid import UUID

from groundwire.temporal.payloads import ApprovalDecision, RunWorkflowInput


class TemporalPort(Protocol):
    async def start_run_workflow(self, input: RunWorkflowInput) -> None: ...

    async def signal_approval(self, run_id: UUID, decision: ApprovalDecision) -> None: ...
