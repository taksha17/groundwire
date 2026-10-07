from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Identity:
    subject: str
    username: str
    tenant_id: UUID
    roles: frozenset[str]

    def is_admin(self) -> bool:
        return bool(self.roles & {"groundwire-admin", "admin"})

    def can_operate(self) -> bool:
        return self.is_admin() or bool(self.roles & {"groundwire-operator", "operator"})
