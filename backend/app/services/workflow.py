from __future__ import annotations

import re
import uuid
from typing import Literal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.domain.workflow import (
    ApprovalAction,
    ApprovalDecision,
    ProjectConnectionStatus,
    RunStage,
    RunStatus,
    WorkItemStatus,
    assert_transition_allowed,
)
from app.models.workflow import Approval, AuditEvent, Repository, WorkItem, WorkRun
from app.repositories.workflow import WorkflowRepository
from app.schemas.workflow import (
    ApprovalGateRead,
    ExecutionRunRead,
    PlanApprovalRequest,
    ProjectCreate,
    ProjectRead,
    PullRequestApprovalRequest,
    WorkItemCreate,
    WorkItemRead,
    WorkItemSubmission,
)

COMMIT_SHA_PATTERN = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
ARTIFACT_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class WorkflowService:
    """Enforces ownership, approval gates, state transitions, and durable audit records."""

    def __init__(self, session: AsyncSession) -> None:
        self._repository = WorkflowRepository(session)

    async def create_project(
        self, request: ProjectCreate, *, actor_subject: str, correlation_id: str
    ) -> ProjectRead:
        existing = await self._repository.get_project_by_name(
            actor_subject, request.repository_full_name
        )
        if existing is not None:
            raise ConflictError("This GitHub repository is already connected to your workspace.")

        project = Repository(
            id=uuid.uuid4(),
            owner_subject=actor_subject,
            github_full_name=request.repository_full_name,
            default_branch=request.default_branch,
            github_installation_id=request.github_installation_id,
            # A GitHub App callback must verify access before this changes to active.
            connection_status=ProjectConnectionStatus.PENDING,
        )
        self._repository.session.add(project)
        self._repository.add_audit_event(
            actor_subject=actor_subject,
            action="project.connection_requested",
            entity_type="project",
            entity_id=project.id,
            correlation_id=correlation_id,
            details={"repository_full_name": project.github_full_name},
        )
        await self._repository.flush()
        return self._project_read(project)

    async def list_projects(self, *, actor_subject: str) -> list[ProjectRead]:
        return [
            self._project_read(project)
            for project in await self._repository.list_projects(actor_subject)
        ]

    async def activate_project_after_github_verification(
        self,
        project_id: uuid.UUID,
        *,
        actor_subject: str,
        github_installation_id: int,
        correlation_id: str,
    ) -> ProjectRead:
        """Internal GitHub App callback hook; never a user-controlled HTTP route."""

        project = await self._repository.get_project(project_id, actor_subject)
        if project is None:
            raise NotFoundError("The repository connection request was not found.")
        if project.connection_status is ProjectConnectionStatus.REVOKED:
            raise ConflictError(
                "A revoked repository connection cannot be reactivated "
                "without a new authorization."
            )
        project.github_installation_id = github_installation_id
        project.connection_status = ProjectConnectionStatus.ACTIVE
        self._repository.add_audit_event(
            actor_subject=actor_subject,
            action="project.connection_verified",
            entity_type="project",
            entity_id=project.id,
            correlation_id=correlation_id,
            details={"github_installation_id": github_installation_id},
        )
        await self._repository.flush()
        return self._project_read(project)

    async def create_work_item(
        self, request: WorkItemCreate, *, actor_subject: str, correlation_id: str
    ) -> WorkItemSubmission:
        project = await self._repository.get_project(request.project_id, actor_subject)
        if project is None:
            raise NotFoundError("The selected project was not found.")
        if project.connection_status is not ProjectConnectionStatus.ACTIVE:
            raise ConflictError(
                "This repository is pending GitHub App verification. "
                "Complete authorization before submitting work."
            )

        work_item = WorkItem(
            id=uuid.uuid4(),
            repository_id=project.id,
            title=request.title.strip(),
            description=request.description.strip(),
            kind=request.kind,
            status=WorkItemStatus.DRAFT,
            failed_ci_url=request.failed_ci_url,
            base_commit_sha=request.base_commit_sha,
        )
        run = WorkRun(
            id=uuid.uuid4(),
            work_item_id=work_item.id,
            stage=RunStage.PLAN,
            status=RunStatus.QUEUED,
            is_current=True,
            base_commit_sha=request.base_commit_sha,
        )
        self._repository.session.add_all([work_item, run])
        self._repository.add_audit_event(
            actor_subject=actor_subject,
            action="work_item.created",
            entity_type="work_item",
            entity_id=work_item.id,
            correlation_id=correlation_id,
            details={"project_id": str(project.id), "kind": request.kind.value},
        )
        self._repository.add_audit_event(
            actor_subject=actor_subject,
            action="run.plan_queued",
            entity_type="run",
            entity_id=run.id,
            correlation_id=correlation_id,
            details={"work_item_id": str(work_item.id)},
        )
        await self._repository.flush()
        return WorkItemSubmission(
            work_item=self._work_item_read(work_item),
            run=await self._execution_run_read(run, work_item),
        )

    async def queue_run_for_worker(
        self,
        work_item_id: uuid.UUID,
        *,
        stage: RunStage,
        actor_subject: str,
        correlation_id: str,
        base_commit_sha: str | None = None,
    ) -> WorkRun:
        """Create the one current attempt for a stage; supersede prior attempts atomically."""

        work_item = await self._repository.get_work_item(
            work_item_id,
            actor_subject,
            for_update=True,
        )
        if work_item is None:
            raise NotFoundError("The work item was not found.")
        if base_commit_sha is not None:
            self._validate_commit_sha(base_commit_sha)
        await self._repository.session.execute(
            update(WorkRun)
            .where(
                WorkRun.work_item_id == work_item.id,
                WorkRun.stage == stage,
                WorkRun.is_current.is_(True),
            )
            .values(is_current=False)
        )
        run = WorkRun(
            id=uuid.uuid4(),
            work_item_id=work_item.id,
            stage=stage,
            status=RunStatus.QUEUED,
            is_current=True,
            base_commit_sha=base_commit_sha,
        )
        self._repository.session.add(run)
        self._repository.add_audit_event(
            actor_subject=actor_subject,
            action="run.queued",
            entity_type="run",
            entity_id=run.id,
            correlation_id=correlation_id,
            details={"work_item_id": str(work_item.id), "stage": stage.value},
        )
        await self._repository.flush()
        return run

    async def complete_run_for_worker(
        self,
        run_id: uuid.UUID,
        *,
        actor_subject: str,
        correlation_id: str,
        pinned_commit_sha: str,
        approval_artifact_sha256: str,
        result_summary: str | None = None,
    ) -> WorkRun:
        """Persist immutable approval material; never update it after success."""

        run = await self._require_locked_run(run_id, actor_subject)
        if not run.is_current:
            raise ConflictError("A superseded run cannot be completed or presented for approval.")
        if run.status not in {RunStatus.QUEUED, RunStatus.RUNNING}:
            raise ConflictError("Only queued or running work can be marked complete.")
        self._validate_commit_sha(pinned_commit_sha)
        self._validate_artifact_sha256(approval_artifact_sha256)
        if (
            run.base_commit_sha is not None
            and run.base_commit_sha.lower() != pinned_commit_sha.lower()
        ):
            raise ConflictError(
                "The worker cannot change a run's already pinned repository commit."
            )
        run.base_commit_sha = pinned_commit_sha.lower()
        run.approval_artifact_sha256 = approval_artifact_sha256.lower()
        run.result_summary = result_summary.strip() if result_summary else None
        run.status = RunStatus.SUCCEEDED
        self._repository.add_audit_event(
            actor_subject=actor_subject,
            action="run.completed",
            entity_type="run",
            entity_id=run.id,
            correlation_id=correlation_id,
            details={
                "work_item_id": str(run.work_item_id),
                "stage": run.stage.value,
                "pinned_commit_sha": run.base_commit_sha,
                "approval_artifact_sha256": run.approval_artifact_sha256,
            },
        )
        await self._repository.flush()
        return run

    async def list_work_items(
        self, *, actor_subject: str, project_id: uuid.UUID | None
    ) -> list[WorkItemRead]:
        return [
            self._work_item_read(item)
            for item in await self._repository.list_work_items(actor_subject, project_id)
        ]

    async def get_execution_run(self, run_id: uuid.UUID, *, actor_subject: str) -> ExecutionRunRead:
        run = await self._require_run(run_id, actor_subject)
        return await self._execution_run_read(run, run.work_item)

    async def record_plan_approval(
        self,
        run_id: uuid.UUID,
        request: PlanApprovalRequest,
        *,
        actor_subject: str,
        correlation_id: str,
    ) -> ExecutionRunRead:
        run = await self._require_locked_run(run_id, actor_subject)
        if run.stage is not RunStage.PLAN or run.status is not RunStatus.SUCCEEDED:
            raise ConflictError("A plan can only be approved after its planning run has completed.")
        if run.work_item.status is not WorkItemStatus.PLAN_AWAITING_APPROVAL:
            raise ConflictError("This work item is not waiting for plan approval.")
        decision = (
            ApprovalDecision.APPROVED
            if request.decision == "approve"
            else ApprovalDecision.REJECTED
        )
        await self._record_approval(
            run,
            action=ApprovalAction.PLAN,
            decision=decision,
            comment=request.comment,
            actor_subject=actor_subject,
            correlation_id=correlation_id,
        )
        return await self._execution_run_read(run, run.work_item)

    async def record_pull_request_approval(
        self,
        run_id: uuid.UUID,
        request: PullRequestApprovalRequest,
        *,
        actor_subject: str,
        correlation_id: str,
    ) -> ExecutionRunRead:
        run = await self._require_locked_run(run_id, actor_subject)
        if run.stage is not RunStage.PULL_REQUEST or run.status is not RunStatus.SUCCEEDED:
            raise ConflictError(
                "Branch and pull-request creation can only be approved after review is complete."
            )
        if run.work_item.status is not WorkItemStatus.PR_AWAITING_APPROVAL:
            raise ConflictError("This work item is not waiting for pull-request approval.")
        await self._record_approval(
            run,
            action=ApprovalAction.PULL_REQUEST,
            decision=ApprovalDecision.APPROVED,
            comment=request.comment,
            actor_subject=actor_subject,
            correlation_id=correlation_id,
        )
        return await self._execution_run_read(run, run.work_item)

    async def transition_work_item_for_worker(
        self,
        work_item_id: uuid.UUID,
        *,
        target: WorkItemStatus,
        actor_subject: str,
        correlation_id: str,
        authorization_run_id: uuid.UUID | None = None,
    ) -> WorkItem:
        """Internal worker-only hook. It is deliberately not exposed by an API route."""

        work_item = await self._repository.get_work_item(
            work_item_id,
            actor_subject,
            for_update=True,
        )
        if work_item is None:
            raise NotFoundError("The work item was not found.")
        previous = work_item.status
        assert_transition_allowed(previous, target)
        if target is WorkItemStatus.PATCH_READY:
            await self._require_approved_gate(
                work_item_id=work_item.id,
                run_id=self._require_authorization_run_id(authorization_run_id),
                expected_stage=RunStage.PLAN,
                action=ApprovalAction.PLAN,
            )
        if target is WorkItemStatus.COMPLETE:
            await self._require_approved_gate(
                work_item_id=work_item.id,
                run_id=self._require_authorization_run_id(authorization_run_id),
                expected_stage=RunStage.PULL_REQUEST,
                action=ApprovalAction.PULL_REQUEST,
            )
        if target is WorkItemStatus.DRAFT:
            await self._invalidate_approval_runs(work_item.id)
        updated_work_item_id = await self._repository.session.scalar(
            update(WorkItem)
            .where(WorkItem.id == work_item.id, WorkItem.status == previous)
            .values(status=target)
            .returning(WorkItem.id)
            .execution_options(synchronize_session=False)
        )
        if updated_work_item_id is None:
            raise ConflictError(
                "The work item changed while its approval gate was being verified. "
                "Retry the operation."
            )
        await self._repository.session.refresh(work_item)
        self._repository.add_audit_event(
            actor_subject=actor_subject,
            action="work_item.transitioned",
            entity_type="work_item",
            entity_id=work_item.id,
            correlation_id=correlation_id,
            details={"from": previous.value, "to": target.value},
        )
        await self._repository.flush()
        return work_item

    async def _require_approved_gate(
        self,
        *,
        work_item_id: uuid.UUID,
        run_id: uuid.UUID,
        expected_stage: RunStage,
        action: ApprovalAction,
    ) -> None:
        result = await self._repository.session.execute(
            select(Approval)
            .join(WorkRun, Approval.run_id == WorkRun.id)
            .where(
                Approval.run_id == run_id,
                WorkRun.work_item_id == work_item_id,
                WorkRun.id == run_id,
                WorkRun.stage == expected_stage,
                WorkRun.is_current.is_(True),
                WorkRun.status == RunStatus.SUCCEEDED,
                Approval.action == action,
                Approval.decision == ApprovalDecision.APPROVED,
                Approval.pinned_commit_sha == WorkRun.base_commit_sha,
                Approval.artifact_sha256 == WorkRun.approval_artifact_sha256,
            )
            .with_for_update(of=(WorkRun, Approval))
        )
        if result.scalar_one_or_none() is None:
            raise ConflictError(
                "The required current-run approval is missing, stale, "
                "or bound to different immutable evidence."
            )

    async def _invalidate_approval_runs(self, work_item_id: uuid.UUID) -> None:
        """A reset invalidates every approval-capable attempt before a new attempt can be queued."""

        await self._repository.session.execute(
            update(WorkRun)
            .where(
                WorkRun.work_item_id == work_item_id,
                WorkRun.stage.in_([RunStage.PLAN, RunStage.PULL_REQUEST]),
                WorkRun.is_current.is_(True),
            )
            .values(is_current=False)
        )

    @staticmethod
    def _require_authorization_run_id(run_id: uuid.UUID | None) -> uuid.UUID:
        if run_id is None:
            raise ConflictError(
                "An exact current run ID is required for this " "approval-gated transition."
            )
        return run_id

    async def _record_approval(
        self,
        run: WorkRun,
        *,
        action: ApprovalAction,
        decision: ApprovalDecision,
        comment: str | None,
        actor_subject: str,
        correlation_id: str,
    ) -> Approval:
        existing = await self._repository.get_approval(run.id, action)
        if existing is not None:
            raise ConflictError("This approval gate has already been decided.")
        pinned_commit_sha, artifact_sha256 = self._approval_material(run)
        approval = Approval(
            id=uuid.uuid4(),
            run_id=run.id,
            action=action,
            decision=decision,
            actor_subject=actor_subject,
            pinned_commit_sha=pinned_commit_sha,
            artifact_sha256=artifact_sha256,
            comment=comment.strip() if comment else None,
        )
        self._repository.session.add(approval)
        self._repository.add_audit_event(
            actor_subject=actor_subject,
            action=f"approval.{action.value}.{decision.value}",
            entity_type="run",
            entity_id=run.id,
            correlation_id=correlation_id,
            details={"work_item_id": str(run.work_item_id)},
        )
        await self._repository.flush()
        return approval

    def _approval_material(self, run: WorkRun) -> tuple[str, str]:
        if not run.is_current:
            raise ConflictError("A superseded run cannot be approved.")
        if run.base_commit_sha is None or run.approval_artifact_sha256 is None:
            raise ConflictError(
                "Approval requires a pinned commit and immutable artifact digest "
                "from the current run."
            )
        self._validate_commit_sha(run.base_commit_sha)
        self._validate_artifact_sha256(run.approval_artifact_sha256)
        return run.base_commit_sha.lower(), run.approval_artifact_sha256.lower()

    @staticmethod
    def _validate_commit_sha(value: str) -> None:
        if not COMMIT_SHA_PATTERN.fullmatch(value):
            raise ConflictError(
                "A pinned repository commit must be a full 40-character SHA-1 "
                "or 64-character SHA-256."
            )

    @staticmethod
    def _validate_artifact_sha256(value: str) -> None:
        if not ARTIFACT_SHA256_PATTERN.fullmatch(value):
            raise ConflictError(
                "An approval artifact digest must be a 64 character SHA-256 hex value."
            )

    async def _require_run(self, run_id: uuid.UUID, actor_subject: str) -> WorkRun:
        run = await self._repository.get_run(run_id, actor_subject)
        if run is None:
            raise NotFoundError("The requested run was not found.")
        return run

    async def _require_locked_run(self, run_id: uuid.UUID, actor_subject: str) -> WorkRun:
        """Lock work-item then run and refresh both before a lifecycle mutation."""

        candidate = await self._require_run(run_id, actor_subject)
        work_item = await self._repository.get_work_item(
            candidate.work_item_id,
            actor_subject,
            for_update=True,
        )
        if work_item is None:
            raise NotFoundError("The work item for the requested run was not found.")
        run = await self._repository.get_run(run_id, actor_subject, for_update=True)
        if run is None:
            raise NotFoundError("The requested run was not found.")
        return run

    async def _execution_run_read(self, run: WorkRun, work_item: WorkItem) -> ExecutionRunRead:
        approvals = await self._repository.list_approvals(run.id)
        approval_by_action = {approval.action: approval for approval in approvals}
        events = await self._repository.list_audit_events([work_item.id, run.id])
        return ExecutionRunRead(
            id=run.id,
            project_id=work_item.repository_id,
            work_item=self._work_item_read(work_item),
            status=work_item.status,
            repository_commit_sha=run.base_commit_sha or work_item.base_commit_sha,
            plan=None,
            plan_approval=self._approval_gate(
                approval_by_action.get(ApprovalAction.PLAN),
                pending=work_item.status is WorkItemStatus.PLAN_AWAITING_APPROVAL,
            ),
            pull_request_approval=self._approval_gate(
                approval_by_action.get(ApprovalAction.PULL_REQUEST),
                pending=work_item.status is WorkItemStatus.PR_AWAITING_APPROVAL,
            ),
            timeline=[self._timeline_event(event) for event in events],
            patch_summary=run.result_summary,
            changed_paths=[],
            check_evidence=[],
            pull_request=None,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    @staticmethod
    def _project_read(project: Repository) -> ProjectRead:
        return ProjectRead(
            id=project.id,
            repository_full_name=project.github_full_name,
            default_branch=project.default_branch,
            connection_status=project.connection_status.value,
            created_at=project.created_at,
        )

    @staticmethod
    def _work_item_read(work_item: WorkItem) -> WorkItemRead:
        return WorkItemRead(
            id=work_item.id,
            project_id=work_item.repository_id,
            title=work_item.title,
            description=work_item.description,
            kind=work_item.kind,
            status=work_item.status,
            failed_ci_url=work_item.failed_ci_url,
            created_at=work_item.created_at,
            updated_at=work_item.updated_at,
        )

    @staticmethod
    def _approval_gate(approval: Approval | None, *, pending: bool) -> ApprovalGateRead:
        if approval is None:
            return ApprovalGateRead(status="pending" if pending else "not_required")
        status: Literal["approved", "rejected"] = (
            "approved" if approval.decision is ApprovalDecision.APPROVED else "rejected"
        )
        return ApprovalGateRead(
            status=status, decided_at=approval.created_at, comment=approval.comment
        )

    @staticmethod
    def _timeline_event(event: AuditEvent) -> dict[str, object]:
        # Audit events are the server source of truth for this user-visible timeline.
        return {
            "id": str(event.id),
            "occurred_at": event.created_at,
            "title": event.action.replace(".", " ").replace("_", " ").title(),
            "detail": "Recorded by CodexForge.",
            "state": "complete",
        }
