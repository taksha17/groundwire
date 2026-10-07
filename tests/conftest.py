import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from groundwire.api import app, get_session, get_temporal
from groundwire.db import Base, make_engine, make_session_factory
from groundwire.temporal.payloads import ApprovalDecision, RunWorkflowInput


class FakeTemporal:
    def __init__(self) -> None:
        self.started: list[RunWorkflowInput] = []
        self.signals: list[ApprovalDecision] = []

    async def start_run_workflow(self, input: RunWorkflowInput) -> None:
        self.started.append(input)

    async def signal_approval(self, run_id, decision: ApprovalDecision) -> None:
        self.signals.append(decision)


@pytest.fixture
def fake_temporal() -> FakeTemporal:
    return FakeTemporal()


@pytest_asyncio.fixture
async def engine() -> AsyncEngine:
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return make_session_factory(engine)


@pytest_asyncio.fixture
async def client(fake_temporal: FakeTemporal, session_factory: async_sessionmaker[AsyncSession]):
    async def override_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_temporal] = lambda: fake_temporal
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
