from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import PrincipalDep, SessionDep
from app.core.errors import ConflictError
from app.schemas.workflow import ProjectCreate, ProjectRead
from app.services.idempotency import IdempotencyService
from app.services.workflow import WorkflowService

router = APIRouter()


@router.get("", response_model=list[ProjectRead])
async def list_projects(session: SessionDep, principal: PrincipalDep) -> list[ProjectRead]:
    return await WorkflowService(session).list_projects(actor_subject=principal.subject)


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    request: Request,
    session: SessionDep,
    principal: PrincipalDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ProjectRead | JSONResponse:
    if payload.idempotency_key is not None and payload.idempotency_key != idempotency_key:
        raise ConflictError(
            "The idempotency key in the request body must match the Idempotency-Key header."
        )
    idempotency = IdempotencyService(session)
    reservation = await idempotency.reserve(
        actor_subject=principal.subject,
        scope="projects.create",
        key=idempotency_key or "",
        payload=payload.model_dump(mode="json", exclude={"idempotency_key"}),
    )
    if reservation.replayed_response is not None:
        replay_status, replay_body = reservation.replayed_response
        return JSONResponse(status_code=replay_status, content=replay_body)

    project = await WorkflowService(session).create_project(
        payload,
        actor_subject=principal.subject,
        correlation_id=request.state.correlation_id,
    )
    response_body = project.model_dump(mode="json")
    await idempotency.complete(
        reservation, status_code=status.HTTP_201_CREATED, response_body=response_body
    )
    await session.commit()
    return project
