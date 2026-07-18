from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.workflow import (
    ApprovalAction,
    ApprovalDecision,
    RunStage,
    RunStatus,
    WorkItemKind,
    WorkItemStatus,
)

GITHUB_FULL_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$"
COMMIT_SHA_PATTERN = r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$"


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository_full_name: str = Field(
        min_length=3, max_length=201, pattern=GITHUB_FULL_NAME_PATTERN
    )
    default_branch: str = Field(default="main", min_length=1, max_length=255)
    github_installation_id: int | None = Field(default=None, ge=1)
    idempotency_key: str | None = Field(default=None, min_length=16, max_length=128)

    @field_validator("repository_full_name")
    @classmethod
    def normalize_repository_name(cls, value: str) -> str:
        return value.strip().lower()


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra="forbid")

    id: uuid.UUID
    repository_full_name: str = Field(
        validation_alias="github_full_name", serialization_alias="repository_full_name"
    )
    default_branch: str
    connection_status: Literal["active", "revoked", "pending"]
    created_at: datetime


class WorkItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: uuid.UUID
    title: str = Field(min_length=3, max_length=280)
    description: str = Field(min_length=10, max_length=20_000)
    kind: WorkItemKind
    failed_ci_url: str | None = Field(default=None, max_length=500)
    base_commit_sha: str | None = Field(default=None, pattern=COMMIT_SHA_PATTERN)
    idempotency_key: str | None = Field(default=None, min_length=16, max_length=128)


class WorkItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra="forbid")

    id: uuid.UUID
    project_id: uuid.UUID = Field(
        validation_alias="repository_id", serialization_alias="project_id"
    )
    title: str
    description: str
    kind: WorkItemKind
    status: WorkItemStatus
    failed_ci_url: str | None
    created_at: datetime
    updated_at: datetime


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra="forbid")

    id: uuid.UUID
    work_item_id: uuid.UUID
    stage: RunStage
    status: RunStatus
    model_name: str | None
    base_commit_sha: str | None
    result_summary: str | None
    created_at: datetime
    updated_at: datetime


class PlanApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]
    comment: str | None = Field(default=None, max_length=2_000)


class PullRequestApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approve_branch_and_pull_request_creation: Literal[True]
    comment: str | None = Field(default=None, max_length=2_000)


class ApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra="forbid")

    id: uuid.UUID
    run_id: uuid.UUID
    action: ApprovalAction
    decision: ApprovalDecision
    comment: str | None
    created_at: datetime


class WorkItemSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_item: WorkItemRead
    run: ExecutionRunRead


class ApprovalGateRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["not_required", "pending", "approved", "rejected"]
    decided_at: datetime | None = None
    comment: str | None = None


class ExecutionRunRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    project_id: uuid.UUID
    work_item: WorkItemRead
    status: WorkItemStatus
    repository_commit_sha: str | None = None
    plan: dict[str, object] | None = None
    plan_approval: ApprovalGateRead
    pull_request_approval: ApprovalGateRead
    timeline: list[dict[str, object]] = Field(default_factory=list)
    patch_summary: str | None = None
    changed_paths: list[str] = Field(default_factory=list)
    check_evidence: list[dict[str, object]] = Field(default_factory=list)
    pull_request: dict[str, object] | None = None
    created_at: datetime
    updated_at: datetime


WorkItemSubmission.model_rebuild()
