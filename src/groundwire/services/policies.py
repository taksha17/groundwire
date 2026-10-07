from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from groundwire.identity import Identity
from groundwire.models import AccessPolicy

_BUILTIN: dict[str, tuple[bool, tuple[str, ...]]] = {
    "groundwire-admin": (True, ("*",)),
    "admin": (True, ("*",)),
    "groundwire-operator": (False, ("*",)),
    "operator": (False, ("*",)),
}


class PolicyDeniedError(Exception):
    pass


async def _permissions(session: AsyncSession, identity: Identity) -> tuple[bool, set[str]]:
    result = await session.execute(
        select(AccessPolicy).where(
            AccessPolicy.tenant_id == identity.tenant_id,
            AccessPolicy.role.in_(list(identity.roles)),
        )
    )
    rows = list(result.scalars().all())
    can_register = False
    tools: set[str] = set()
    if rows:
        for row in rows:
            can_register = can_register or row.can_register_agents
            tools.update(str(tool) for tool in row.approvable_tools)
        return can_register, tools
    for role in identity.roles:
        builtin = _BUILTIN.get(role)
        if builtin is None:
            continue
        can_register = can_register or builtin[0]
        tools.update(builtin[1])
    return can_register, tools


def _tool_allowed(tools: set[str], tool: str | None) -> bool:
    if "*" in tools:
        return True
    if tool is None:
        return bool(tools)
    return tool in tools


async def assert_can_register(session: AsyncSession, identity: Identity) -> None:
    can_register, _ = await _permissions(session, identity)
    if not can_register:
        raise PolicyDeniedError("register_agent")


async def assert_can_approve(session: AsyncSession, identity: Identity, tool: str | None) -> None:
    _, tools = await _permissions(session, identity)
    if not _tool_allowed(tools, tool):
        raise PolicyDeniedError("approve")


async def seed_default_policies(session: AsyncSession, tenant_id: UUID) -> None:
    existing = await session.execute(
        select(AccessPolicy).where(AccessPolicy.tenant_id == tenant_id)
    )
    if existing.scalars().first() is not None:
        return
    session.add(
        AccessPolicy(
            tenant_id=tenant_id,
            role="groundwire-admin",
            can_register_agents=True,
            approvable_tools=["*"],
        )
    )
    session.add(
        AccessPolicy(
            tenant_id=tenant_id,
            role="groundwire-operator",
            can_register_agents=False,
            approvable_tools=["*"],
        )
    )
    await session.commit()
