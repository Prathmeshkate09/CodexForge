from __future__ import annotations

from enum import StrEnum

from app.core.errors import ConflictError


class WorkItemKind(StrEnum):
    BUG = "bug"
    FEATURE = "feature"
    FAILED_CI = "failed_ci"


class ProjectConnectionStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    REVOKED = "revoked"


class WorkItemStatus(StrEnum):
    DRAFT = "draft"
    SNAPSHOT_PINNED = "snapshot_pinned"
    PLAN_AWAITING_APPROVAL = "plan_awaiting_approval"
    PATCH_READY = "patch_ready"
    CHECKS_QUEUED = "checks_queued"
    CHECKS_RUNNING = "checks_running"
    REVIEW_READY = "review_ready"
    PR_AWAITING_APPROVAL = "pr_awaiting_approval"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunStage(StrEnum):
    PLAN = "plan"
    PATCH = "patch"
    CHECKS = "checks"
    PULL_REQUEST = "pull_request"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalAction(StrEnum):
    PLAN = "plan"
    PULL_REQUEST = "pull_request"


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


ALLOWED_WORK_ITEM_TRANSITIONS: dict[WorkItemStatus, set[WorkItemStatus]] = {
    WorkItemStatus.DRAFT: {WorkItemStatus.SNAPSHOT_PINNED, WorkItemStatus.CANCELLED},
    WorkItemStatus.SNAPSHOT_PINNED: {
        WorkItemStatus.PLAN_AWAITING_APPROVAL,
        WorkItemStatus.FAILED,
        WorkItemStatus.CANCELLED,
    },
    WorkItemStatus.PLAN_AWAITING_APPROVAL: {
        WorkItemStatus.PATCH_READY,
        WorkItemStatus.DRAFT,
        WorkItemStatus.CANCELLED,
    },
    WorkItemStatus.PATCH_READY: {
        WorkItemStatus.CHECKS_QUEUED,
        WorkItemStatus.CANCELLED,
    },
    WorkItemStatus.CHECKS_QUEUED: {
        WorkItemStatus.CHECKS_RUNNING,
        WorkItemStatus.CANCELLED,
    },
    WorkItemStatus.CHECKS_RUNNING: {
        WorkItemStatus.REVIEW_READY,
        WorkItemStatus.FAILED,
        WorkItemStatus.CANCELLED,
    },
    WorkItemStatus.REVIEW_READY: {
        WorkItemStatus.PR_AWAITING_APPROVAL,
        WorkItemStatus.DRAFT,
        WorkItemStatus.CANCELLED,
    },
    WorkItemStatus.PR_AWAITING_APPROVAL: {
        WorkItemStatus.COMPLETE,
        WorkItemStatus.DRAFT,
        WorkItemStatus.CANCELLED,
    },
    WorkItemStatus.COMPLETE: set(),
    WorkItemStatus.FAILED: {WorkItemStatus.DRAFT, WorkItemStatus.CANCELLED},
    WorkItemStatus.CANCELLED: set(),
}


def assert_transition_allowed(current: WorkItemStatus, target: WorkItemStatus) -> None:
    if target not in ALLOWED_WORK_ITEM_TRANSITIONS[current]:
        raise ConflictError(f"Cannot transition a work item from '{current}' to '{target}'.")
