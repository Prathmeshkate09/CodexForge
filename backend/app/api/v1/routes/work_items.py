from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import PrincipalDep, SessionDep
from app.core.errors import ConflictError
from app.schemas.workflow import WorkItemCreate, WorkItemRead, WorkItemSubmission
from app.services.idempotency import IdempotencyService
from app.services.workflow import WorkflowService

router = APIRouter()


@router.get("", response_model=list[WorkItemRead])
async def list_work_items(
    session: SessionDep,
    principal: PrincipalDep,
    project_id: uuid.UUID | None = Query(default=None),
) -> list[WorkItemRead]:
    return await WorkflowService(session).list_work_items(
        actor_subject=principal.subject, project_id=project_id
    )


@router.post("", response_model=WorkItemSubmission, status_code=status.HTTP_201_CREATED)
async def create_work_item(
    payload: WorkItemCreate,
    request: Request,
    session: SessionDep,
    principal: PrincipalDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> WorkItemSubmission | JSONResponse:
    if payload.idempotency_key is not None and payload.idempotency_key != idempotency_key:
        raise ConflictError(
            "The idempotency key in the request body must match the Idempotency-Key header."
        )
    idempotency = IdempotencyService(session)
    reservation = await idempotency.reserve(
        actor_subject=principal.subject,
        scope="work-items.create",
        key=idempotency_key or "",
        payload=payload.model_dump(mode="json", exclude={"idempotency_key"}),
    )
    if reservation.replayed_response is not None:
        replay_status, replay_body = reservation.replayed_response
        return JSONResponse(status_code=replay_status, content=replay_body)

    submission = await WorkflowService(session).create_work_item(
        payload,
        actor_subject=principal.subject,
        correlation_id=request.state.correlation_id,
    )
    response_body = submission.model_dump(mode="json")
    await idempotency.complete(
        reservation, status_code=status.HTTP_201_CREATED, response_body=response_body
    )
    await session.commit()
    return submission
