import os
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from groundwire.api import app, get_session, get_temporal
from groundwire.db import Base, make_engine, make_session_factory
from groundwire.temporal.payloads import ApprovalDecision, RunWorkflowInput
from tests.jwt_util import AUDIENCE, ISSUER, generate_rsa_pem

_DATA_TMP = Path(__file__).resolve().parents[1] / ".data" / "tmp"
_DATA_TMP.mkdir(parents=True, exist_ok=True)
os.environ["TMPDIR"] = str(_DATA_TMP)
os.environ.setdefault("AUTH_ENABLED", "false")

TENANT_A = UUID("00000000-0000-0000-0000-000000000001")
TENANT_B = UUID("00000000-0000-0000-0000-000000000002")

AGENT_BODY = {
    "name": "demo-ops-agent",
    "allowed_tools": ["send_email"],
    "approval_policy": {"require_approval_for": ["send_email"]},
}


class FakeTemporal:
    def __init__(self) -> None:
        self.started: list[RunWorkflowInput] = []
        self.signals: list[ApprovalDecision] = []

    async def start_run_workflow(self, input: RunWorkflowInput) -> None:
        self.started.append(input)

    async def signal_approval(self, run_id, decision: ApprovalDecision) -> None:
        self.signals.append(decision)


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def fake_temporal() -> FakeTemporal:
    return FakeTemporal()


@pytest.fixture
def rsa_keys() -> tuple[bytes, bytes]:
    return generate_rsa_pem()


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


@pytest_asyncio.fixture
async def auth_client(
    monkeypatch,
    rsa_keys,
    fake_temporal: FakeTemporal,
    session_factory: async_sessionmaker[AsyncSession],
):
    _, public_pem = rsa_keys
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("OIDC_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("OIDC_PUBLIC_KEY", public_pem.decode())

    async def override_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_temporal] = lambda: fake_temporal
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
