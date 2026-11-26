from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from app.api.deps import PrincipalDep, SessionDep
from app.core.config import get_settings
from app.domain.workflow import WorkItemStatus
from app.schemas.workflow import (
    ExecutionRunRead,
    PlanApprovalRequest,
    PullRequestApprovalRequest,
)
from app.services.patch_worker import PatchWorkerService
from app.services.planning_worker import PlanningWorkerService
from app.services.workflow import WorkflowService

router = APIRouter()


@router.get("/{run_id}", response_model=ExecutionRunRead)
async def get_run(
    run_id: uuid.UUID, session: SessionDep, principal: PrincipalDep
) -> ExecutionRunRead:
    return await WorkflowService(session).get_execution_run(run_id, actor_subject=principal.subject)


@router.post("/{run_id}/generate-plan", response_model=ExecutionRunRead)
async def generate_plan_for_run(
    run_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    principal: PrincipalDep,
) -> ExecutionRunRead:
    worker = PlanningWorkerService(session, get_settings())
    result = await worker.execute_plan_run(
        run_id,
        actor_subject=principal.subject,
        correlation_id=request.state.correlation_id,
    )
    await session.commit()
    return result


@router.post("/{run_id}/generate-patch", response_model=ExecutionRunRead)
async def generate_patch_for_run(
    run_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    principal: PrincipalDep,
) -> ExecutionRunRead:
    worker = PatchWorkerService(session, get_settings())
    result = await worker.execute_patch_worker(
        run_id,
        actor_subject=principal.subject,
        correlation_id=request.state.correlation_id,
    )
    await session.commit()
    return result


@router.post("/{run_id}/plan-approval", response_model=ExecutionRunRead)
async def decide_plan_approval(
    run_id: uuid.UUID,
    payload: PlanApprovalRequest,
    request: Request,
    session: SessionDep,
    principal: PrincipalDep,
) -> ExecutionRunRead:
    workflow = WorkflowService(session)
    result = await workflow.record_plan_approval(
        run_id,
        payload,
        actor_subject=principal.subject,
        correlation_id=request.state.correlation_id,
    )
    if payload.decision == "approve":
        patch_worker = PatchWorkerService(session, get_settings())
        result = await patch_worker.execute_patch_worker(
            run_id,
            actor_subject=principal.subject,
            correlation_id=request.state.correlation_id,
        )
    await session.commit()
    return result


@router.post("/{run_id}/pull-request-approval", response_model=ExecutionRunRead)
async def approve_pull_request_creation(
    run_id: uuid.UUID,
    payload: PullRequestApprovalRequest,
    request: Request,
    session: SessionDep,
    principal: PrincipalDep,
) -> ExecutionRunRead:
    service = WorkflowService(session)
    result = await service.record_pull_request_approval(
        run_id,
        payload,
        actor_subject=principal.subject,
        correlation_id=request.state.correlation_id,
    )
    await service.transition_work_item_for_worker(
        result.work_item.id,
        target=WorkItemStatus.COMPLETE,
        actor_subject=principal.subject,
        correlation_id=request.state.correlation_id,
        authorization_run_id=run_id,
    )
    await session.commit()
    return await service.get_execution_run(run_id, actor_subject=principal.subject)


@router.post("/{run_id}/sync-pr", response_model=ExecutionRunRead)
async def sync_pull_request(
    run_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    principal: PrincipalDep,
) -> ExecutionRunRead:
    service = WorkflowService(session)
    result = await service.sync_github_pull_request_for_run(
        run_id,
        actor_subject=principal.subject,
        correlation_id=request.state.correlation_id,
    )
    await session.commit()
    return result
