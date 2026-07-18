from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.domain.workflow import ApprovalAction, RunStage, WorkItemStatus
from app.models.workflow import WorkItem, WorkRun
from app.schemas.workflow import (
    PlanApprovalRequest,
    ProjectCreate,
    PullRequestApprovalRequest,
    WorkItemCreate,
)
from app.services.workflow import WorkflowService

PINNED_COMMIT = "a" * 40
PLAN_ARTIFACT = "1" * 64
PR_ARTIFACT = "2" * 64


async def _create_work_item(
    session: AsyncSession,
) -> tuple[WorkflowService, uuid.UUID, uuid.UUID]:
    service = WorkflowService(session)
    project = await service.create_project(
        ProjectCreate(repository_full_name="acme/widgets", default_branch="main"),
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )
    await service.activate_project_after_github_verification(
        project.id,
        actor_subject="owner-1",
        github_installation_id=12345,
        correlation_id="test-correlation",
    )
    submission = await service.create_work_item(
        WorkItemCreate(
            project_id=project.id,
            kind="failed_ci",
            title="Repair broken build",
            description="The integration build fails while compiling the API package.",
            failed_ci_url="https://github.com/acme/widgets/actions/runs/123",
        ),
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )
    await session.commit()
    return service, submission.work_item.id, submission.run.id


async def _approved_plan_waiting_for_patch(
    session: AsyncSession,
) -> tuple[WorkflowService, uuid.UUID, uuid.UUID]:
    service, work_item_id, plan_run_id = await _create_work_item(session)
    await service.complete_run_for_worker(
        plan_run_id,
        actor_subject="owner-1",
        correlation_id="test-correlation",
        pinned_commit_sha=PINNED_COMMIT,
        approval_artifact_sha256=PLAN_ARTIFACT,
    )
    await service.transition_work_item_for_worker(
        work_item_id,
        target=WorkItemStatus.SNAPSHOT_PINNED,
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )
    await service.transition_work_item_for_worker(
        work_item_id,
        target=WorkItemStatus.PLAN_AWAITING_APPROVAL,
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )
    await service.record_plan_approval(
        plan_run_id,
        PlanApprovalRequest(decision="approve"),
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )
    return service, work_item_id, plan_run_id


@pytest.mark.asyncio
async def test_owner_cannot_access_another_users_project(session: AsyncSession) -> None:
    service, work_item_id, _ = await _create_work_item(session)
    work_item = await session.get(WorkItem, work_item_id)
    assert work_item is not None
    with pytest.raises(NotFoundError):
        await service.create_work_item(
            WorkItemCreate(
                project_id=work_item.repository_id,
                kind="bug",
                title="Unauthorized access",
                description="This should not disclose whether another user owns a project.",
            ),
            actor_subject="other-user",
            correlation_id="test-correlation",
        )
    assert work_item_id is not None


@pytest.mark.asyncio
async def test_work_item_requires_verified_github_connection(
    session: AsyncSession,
) -> None:
    service = WorkflowService(session)
    project = await service.create_project(
        ProjectCreate(repository_full_name="acme/pending-repository", default_branch="main"),
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )
    with pytest.raises(ConflictError, match="pending GitHub App verification"):
        await service.create_work_item(
            WorkItemCreate(
                project_id=project.id,
                kind="bug",
                title="Attempt work before verification",
                description=(
                    "The service must not process a repository before GitHub access is verified."
                ),
            ),
            actor_subject="owner-1",
            correlation_id="test-correlation",
        )


@pytest.mark.asyncio
async def test_worker_transition_requires_recorded_plan_and_pr_approvals(
    session: AsyncSession,
) -> None:
    service, work_item_id, plan_run_id = await _create_work_item(session)
    await service.complete_run_for_worker(
        plan_run_id,
        actor_subject="owner-1",
        correlation_id="test-correlation",
        pinned_commit_sha=PINNED_COMMIT,
        approval_artifact_sha256=PLAN_ARTIFACT,
    )

    await service.transition_work_item_for_worker(
        work_item_id,
        target=WorkItemStatus.SNAPSHOT_PINNED,
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )
    await service.transition_work_item_for_worker(
        work_item_id,
        target=WorkItemStatus.PLAN_AWAITING_APPROVAL,
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )
    await session.commit()

    with pytest.raises(ConflictError, match="current-run approval"):
        await service.transition_work_item_for_worker(
            work_item_id,
            target=WorkItemStatus.PATCH_READY,
            actor_subject="owner-1",
            correlation_id="test-correlation",
            authorization_run_id=plan_run_id,
        )

    approved_plan = await service.record_plan_approval(
        plan_run_id,
        PlanApprovalRequest(decision="approve", comment="Evidence looks correct."),
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )
    assert approved_plan.plan_approval.status == "approved"
    plan_run = await session.get(WorkRun, plan_run_id)
    assert plan_run is not None
    # Even a same-run approval becomes invalid if its immutable evidence no longer matches.
    plan_run.approval_artifact_sha256 = "f" * 64
    await session.flush()
    with pytest.raises(ConflictError, match="current-run approval"):
        await service.transition_work_item_for_worker(
            work_item_id,
            target=WorkItemStatus.PATCH_READY,
            actor_subject="owner-1",
            correlation_id="test-correlation",
            authorization_run_id=plan_run_id,
        )
    plan_run.approval_artifact_sha256 = PLAN_ARTIFACT
    await session.flush()
    await service.transition_work_item_for_worker(
        work_item_id,
        target=WorkItemStatus.PATCH_READY,
        actor_subject="owner-1",
        correlation_id="test-correlation",
        authorization_run_id=plan_run_id,
    )
    await service.transition_work_item_for_worker(
        work_item_id,
        target=WorkItemStatus.CHECKS_QUEUED,
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )
    await service.transition_work_item_for_worker(
        work_item_id,
        target=WorkItemStatus.CHECKS_RUNNING,
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )
    await service.transition_work_item_for_worker(
        work_item_id,
        target=WorkItemStatus.REVIEW_READY,
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )
    await service.transition_work_item_for_worker(
        work_item_id,
        target=WorkItemStatus.PR_AWAITING_APPROVAL,
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )
    pr_run = await service.queue_run_for_worker(
        work_item_id,
        stage=RunStage.PULL_REQUEST,
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )
    await service.complete_run_for_worker(
        pr_run.id,
        actor_subject="owner-1",
        correlation_id="test-correlation",
        pinned_commit_sha=PINNED_COMMIT,
        approval_artifact_sha256=PR_ARTIFACT,
    )

    with pytest.raises(ConflictError, match="current-run approval"):
        await service.transition_work_item_for_worker(
            work_item_id,
            target=WorkItemStatus.COMPLETE,
            actor_subject="owner-1",
            correlation_id="test-correlation",
            authorization_run_id=pr_run.id,
        )

    approved_pr = await service.record_pull_request_approval(
        pr_run.id,
        PullRequestApprovalRequest(approve_branch_and_pull_request_creation=True),
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )
    assert approved_pr.pull_request_approval.status == "approved"
    completed = await service.transition_work_item_for_worker(
        work_item_id,
        target=WorkItemStatus.COMPLETE,
        actor_subject="owner-1",
        correlation_id="test-correlation",
        authorization_run_id=pr_run.id,
    )
    assert completed.status is WorkItemStatus.COMPLETE


@pytest.mark.asyncio
async def test_reset_retry_cannot_reuse_stale_plan_approval(
    session: AsyncSession,
) -> None:
    service, work_item_id, original_plan_run_id = await _create_work_item(session)
    await service.complete_run_for_worker(
        original_plan_run_id,
        actor_subject="owner-1",
        correlation_id="test-correlation",
        pinned_commit_sha=PINNED_COMMIT,
        approval_artifact_sha256=PLAN_ARTIFACT,
    )
    await service.transition_work_item_for_worker(
        work_item_id,
        target=WorkItemStatus.SNAPSHOT_PINNED,
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )
    await service.transition_work_item_for_worker(
        work_item_id,
        target=WorkItemStatus.PLAN_AWAITING_APPROVAL,
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )
    await service.record_plan_approval(
        original_plan_run_id,
        PlanApprovalRequest(decision="approve"),
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )

    # A reset must revoke the old approval before a replacement plan can be queued.
    await service.transition_work_item_for_worker(
        work_item_id,
        target=WorkItemStatus.DRAFT,
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )
    replacement_plan = await service.queue_run_for_worker(
        work_item_id,
        stage=RunStage.PLAN,
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )
    await service.complete_run_for_worker(
        replacement_plan.id,
        actor_subject="owner-1",
        correlation_id="test-correlation",
        pinned_commit_sha="b" * 40,
        approval_artifact_sha256="3" * 64,
    )
    await service.transition_work_item_for_worker(
        work_item_id,
        target=WorkItemStatus.SNAPSHOT_PINNED,
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )
    await service.transition_work_item_for_worker(
        work_item_id,
        target=WorkItemStatus.PLAN_AWAITING_APPROVAL,
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )

    with pytest.raises(ConflictError, match="current-run approval"):
        await service.transition_work_item_for_worker(
            work_item_id,
            target=WorkItemStatus.PATCH_READY,
            actor_subject="owner-1",
            correlation_id="test-correlation",
            authorization_run_id=original_plan_run_id,
        )

    await service.record_plan_approval(
        replacement_plan.id,
        PlanApprovalRequest(decision="approve"),
        actor_subject="owner-1",
        correlation_id="test-correlation",
    )
    transitioned = await service.transition_work_item_for_worker(
        work_item_id,
        target=WorkItemStatus.PATCH_READY,
        actor_subject="owner-1",
        correlation_id="test-correlation",
        authorization_run_id=replacement_plan.id,
    )
    assert transitioned.status is WorkItemStatus.PATCH_READY


@pytest.mark.asyncio
async def test_approval_transition_fails_closed_when_reset_interleaves_after_gate(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, work_item_id, plan_run_id = await _approved_plan_waiting_for_patch(session)
    original_gate = service._require_approved_gate

    async def reset_after_verified_gate(
        *,
        work_item_id: uuid.UUID,
        run_id: uuid.UUID,
        expected_stage: RunStage,
        action: ApprovalAction,
    ) -> None:
        await original_gate(
            work_item_id=work_item_id,
            run_id=run_id,
            expected_stage=expected_stage,
            action=action,
        )
        await service.transition_work_item_for_worker(
            work_item_id,
            target=WorkItemStatus.DRAFT,
            actor_subject="owner-1",
            correlation_id="interleaved-reset",
        )

    monkeypatch.setattr(service, "_require_approved_gate", reset_after_verified_gate)

    with pytest.raises(ConflictError, match="changed while its approval gate"):
        await service.transition_work_item_for_worker(
            work_item_id,
            target=WorkItemStatus.PATCH_READY,
            actor_subject="owner-1",
            correlation_id="stale-patch-transition",
            authorization_run_id=plan_run_id,
        )

    work_item = await session.get(WorkItem, work_item_id)
    plan_run = await session.get(WorkRun, plan_run_id)
    assert work_item is not None
    assert plan_run is not None
    assert work_item.status is WorkItemStatus.DRAFT
    assert plan_run.is_current is False


@pytest.mark.asyncio
async def test_approval_material_requires_a_canonical_full_commit_id(
    session: AsyncSession,
) -> None:
    service, _, plan_run_id = await _create_work_item(session)

    with pytest.raises(ConflictError, match="full 40-character SHA-1"):
        await service.complete_run_for_worker(
            plan_run_id,
            actor_subject="owner-1",
            correlation_id="test-correlation",
            pinned_commit_sha="a" * 39,
            approval_artifact_sha256=PLAN_ARTIFACT,
        )


def test_work_item_schema_rejects_abbreviated_base_commit_id() -> None:
    with pytest.raises(ValueError, match="pattern"):
        WorkItemCreate(
            project_id=uuid.uuid4(),
            kind="bug",
            title="Reject short commit ID",
            description="The submitted base commit must be a canonical full object ID.",
            base_commit_sha="a" * 39,
        )


@pytest.mark.asyncio
async def test_illegal_state_transition_is_rejected(session: AsyncSession) -> None:
    service, work_item_id, _ = await _create_work_item(session)
    with pytest.raises(ConflictError, match="Cannot transition"):
        await service.transition_work_item_for_worker(
            work_item_id,
            target=WorkItemStatus.CHECKS_RUNNING,
            actor_subject="owner-1",
            correlation_id="test-correlation",
        )
