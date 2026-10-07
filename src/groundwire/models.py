from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from groundwire.db import Base
from groundwire.enums import RunStatus, StepStatus, StepType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentDefinition(Base):
    __tablename__ = "agent_definitions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    allowed_tools: Mapped[list] = mapped_column(JSON().with_variant(SQLITE_JSON(), "sqlite"), nullable=False)
    approval_policy: Mapped[dict] = mapped_column(JSON().with_variant(SQLITE_JSON(), "sqlite"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    runs: Mapped[list["Run"]] = relationship(back_populates="agent_definition")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    agent_definition_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("agent_definitions.id"), nullable=False
    )
    agent_version: Mapped[int] = mapped_column(Integer, nullable=False)
    temporal_workflow_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default=RunStatus.PLANNING)
    payload: Mapped[dict] = mapped_column(JSON().with_variant(SQLITE_JSON(), "sqlite"), nullable=False)
    current_step: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pending_action: Mapped[dict | None] = mapped_column(
        JSON().with_variant(SQLITE_JSON(), "sqlite"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    agent_definition: Mapped[AgentDefinition] = relationship(back_populates="runs")
    steps: Mapped[list["Step"]] = relationship(back_populates="run")
    audit_records: Mapped[list["AuditRecord"]] = relationship(back_populates="run")


class Step(Base):
    __tablename__ = "steps"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("runs.id"), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False, default=StepType.TOOL_CALL)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default=StepStatus.PENDING)
    input_payload: Mapped[dict | None] = mapped_column(
        JSON().with_variant(SQLITE_JSON(), "sqlite"), nullable=True
    )
    output_payload: Mapped[dict | None] = mapped_column(
        JSON().with_variant(SQLITE_JSON(), "sqlite"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    run: Mapped[Run] = relationship(back_populates="steps")


class AccessPolicy(Base):
    __tablename__ = "access_policies"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    can_register_agents: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approvable_tools: Mapped[list] = mapped_column(
        JSON().with_variant(SQLITE_JSON(), "sqlite"), nullable=False
    )


class AuditRecord(Base):
    __tablename__ = "audit_records"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    run_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("runs.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON().with_variant(SQLITE_JSON(), "sqlite"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    run: Mapped[Run] = relationship(back_populates="audit_records")
