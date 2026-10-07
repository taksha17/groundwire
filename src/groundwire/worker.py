import asyncio
import logging

from temporalio.worker import Worker

from groundwire.db import create_tables, make_engine, make_session_factory
from groundwire.settings import get_settings
from groundwire.temporal.client import connect_temporal_sdk
from groundwire.temporal.activities import (
    configure_activities,
    execute_tool,
    persist_run_progress,
    plan_run,
    route_model,
    write_audit,
)
from groundwire.temporal.workflows import AgentRunWorkflow

logger = logging.getLogger(__name__)


async def run_worker() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    await create_tables(engine)
    factory = make_session_factory(engine)
    configure_activities(factory)
    client = await connect_temporal_sdk(settings)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[AgentRunWorkflow],
        activities=[persist_run_progress, write_audit, plan_run, route_model, execute_tool],
    )
    logger.info("Groundwire worker listening on %s", settings.temporal_task_queue)
    try:
        await worker.run()
    finally:
        await engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
