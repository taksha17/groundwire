from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from groundwire.models import AgentDefinition
from groundwire.schemas import ApprovalPolicy
from groundwire.settings import DEFAULT_TENANT_ID


async def register_agent(
    session: AsyncSession,
    *,
    name: str,
    allowed_tools: list[str],
    approval_policy: ApprovalPolicy,
    tenant_id: UUID | None = None,
) -> AgentDefinition:
    agent = AgentDefinition(
        tenant_id=tenant_id or DEFAULT_TENANT_ID,
        name=name,
        allowed_tools=allowed_tools,
        approval_policy=approval_policy.model_dump(),
        version=1,
    )
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return agent


async def get_agent(session: AsyncSession, agent_id: UUID) -> AgentDefinition | None:
    result = await session.execute(select(AgentDefinition).where(AgentDefinition.id == agent_id))
    return result.scalar_one_or_none()


async def list_agents(session: AsyncSession) -> list[AgentDefinition]:
    result = await session.execute(
        select(AgentDefinition).order_by(AgentDefinition.created_at.desc())
    )
    return list(result.scalars().all())
