from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.domain.workflow import (
    ApprovalAction,
    ApprovalDecision,
    ProjectConnectionStatus,
    RunStage,
    RunStatus,
    WorkItemKind,
    WorkItemStatus,
)


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_class]


class TimestampedEntity:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Repository(TimestampedEntity, Base):
    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint(
            "owner_subject", "github_full_name", name="uq_repositories_owner_full_name"
        ),
        Index("ix_repositories_owner_created", "owner_subject", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_subject: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    github_full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(255), nullable=False, default="main")
    connection_status: Mapped[ProjectConnectionStatus] = mapped_column(
        Enum(
            ProjectConnectionStatus,
            name="project_connection_status",
            values_callable=_enum_values,
        ),
        nullable=False,
        default=ProjectConnectionStatus.PENDING,
    )
    github_installation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    work_items: Mapped[list[WorkItem]] = relationship(back_populates="repository", lazy="raise")


class WorkItem(TimestampedEntity, Base):
    __tablename__ = "work_items"
    __table_args__ = (Index("ix_work_items_repository_status", "repository_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(280), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[WorkItemKind] = mapped_column(
        Enum(WorkItemKind, name="work_item_kind", values_callable=_enum_values),
        nullable=False,
    )
    status: Mapped[WorkItemStatus] = mapped_column(
        Enum(WorkItemStatus, name="work_item_status", values_callable=_enum_values),
        nullable=False,
        default=WorkItemStatus.DRAFT,
        index=True,
    )
    failed_ci_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    base_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    repository: Mapped[Repository] = relationship(back_populates="work_items", lazy="raise")
    runs: Mapped[list[WorkRun]] = relationship(back_populates="work_item", lazy="raise")


class WorkRun(TimestampedEntity, Base):
    __tablename__ = "work_runs"
    __table_args__ = (
        Index(
            "ix_work_runs_work_item_stage_created",
            "work_item_id",
            "stage",
            "created_at",
        ),
        Index(
            "ix_work_runs_work_item_stage_current",
            "work_item_id",
            "stage",
            "is_current",
        ),
        Index(
            "uq_work_runs_current_stage",
            "work_item_id",
            "stage",
            unique=True,
            postgresql_where=text("is_current"),
            sqlite_where=text("is_current"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[RunStage] = mapped_column(
        Enum(RunStage, name="run_stage", values_callable=_enum_values), nullable=False
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, name="run_status", values_callable=_enum_values),
        nullable=False,
        default=RunStatus.QUEUED,
        index=True,
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    base_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Worker-set SHA-256 for the immutable artifact presented for approval.
    approval_artifact_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_response_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # This stores a redacted continuation transcript with only output and tool-call IDs.
    provider_output_items: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    provider_tool_call_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    safety_identifier_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_item: Mapped[WorkItem] = relationship(back_populates="runs", lazy="raise")
    approvals: Mapped[list[Approval]] = relationship(back_populates="run", lazy="raise")


class Approval(TimestampedEntity, Base):
    __tablename__ = "approvals"
    __table_args__ = (UniqueConstraint("run_id", "action", name="uq_approvals_run_action"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[ApprovalAction] = mapped_column(
        Enum(ApprovalAction, name="approval_action", values_callable=_enum_values),
        nullable=False,
    )
    decision: Mapped[ApprovalDecision] = mapped_column(
        Enum(ApprovalDecision, name="approval_decision", values_callable=_enum_values),
        nullable=False,
    )
    actor_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    # Immutable material from the exact run; a later retry cannot reuse approval.
    pinned_commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    run: Mapped[WorkRun] = relationship(back_populates="approvals", lazy="raise")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_subject_created", "actor_subject", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_subject: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("actor_subject", "scope", "key", name="uq_idempotency_actor_scope_key"),
        Index("ix_idempotency_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[str] = mapped_column(String(160), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
