from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from app.api.deps import PrincipalDep, SessionDep
from app.schemas.workflow import (
    ExecutionRunRead,
    PlanApprovalRequest,
    PullRequestApprovalRequest,
)
from app.services.workflow import WorkflowService

router = APIRouter()


@router.get("/{run_id}", response_model=ExecutionRunRead)
async def get_run(
    run_id: uuid.UUID, session: SessionDep, principal: PrincipalDep
) -> ExecutionRunRead:
    return await WorkflowService(session).get_execution_run(run_id, actor_subject=principal.subject)


@router.post("/{run_id}/plan-approval", response_model=ExecutionRunRead)
async def decide_plan_approval(
    run_id: uuid.UUID,
    payload: PlanApprovalRequest,
    request: Request,
    session: SessionDep,
    principal: PrincipalDep,
) -> ExecutionRunRead:
    result = await WorkflowService(session).record_plan_approval(
        run_id,
        payload,
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
    result = await WorkflowService(session).record_pull_request_approval(
        run_id,
        payload,
        actor_subject=principal.subject,
        correlation_id=request.state.correlation_id,
    )
    await session.commit()
    return result
