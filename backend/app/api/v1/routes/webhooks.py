from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import SessionDep, get_app_settings
from app.core.errors import AuthorizationError
from app.core.github_auth import verify_github_webhook_signature
from app.services.idempotency import IdempotencyService
from app.services.workflow import WorkflowService

router = APIRouter()


@router.post("/github", status_code=status.HTTP_200_OK)
async def receive_github_webhook(
    request: Request,
    session: SessionDep,
    signature_header: Annotated[str | None, Header(alias="X-Hub-Signature-256")] = None,
    event_type: Annotated[str | None, Header(alias="X-GitHub-Event")] = None,
    delivery_id: Annotated[str | None, Header(alias="X-GitHub-Delivery")] = None,
) -> JSONResponse:
    settings = get_app_settings(request)
    body_bytes = await request.body()
    verify_github_webhook_signature(settings, body_bytes, signature_header)

    if not event_type:
        raise AuthorizationError("Missing X-GitHub-Event header.")

    if event_type == "ping":
        return JSONResponse(status_code=200, content={"status": "ok", "message": "pong"})

    try:
        payload: dict[str, Any] = json.loads(body_bytes.decode("utf-8"))
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"detail": f"Malformed JSON: {exc}"})

    # Optional deduplication by delivery ID
    idempotency = IdempotencyService(session)
    reservation = None
    if delivery_id and len(delivery_id) >= 16:
        reservation = await idempotency.reserve(
            actor_subject="github-webhook",
            scope="webhooks.github",
            key=delivery_id,
            payload=payload,
        )
        if reservation.replayed_response is not None:
            replay_status, replay_body = reservation.replayed_response
            return JSONResponse(status_code=replay_status, content=replay_body)

    correlation_id = getattr(request.state, "correlation_id", "github-webhook")
    service = WorkflowService(session)
    affected_count = 0

    if event_type == "installation_repositories":
        action = payload.get("action", "")
        installation = payload.get("installation", {})
        installation_id = installation.get("id")
        if isinstance(installation_id, int):
            repos_added = [
                repo["full_name"]
                for repo in payload.get("repositories_added", [])
                if isinstance(repo, dict) and "full_name" in repo
            ]
            repos_removed = [
                repo["full_name"]
                for repo in payload.get("repositories_removed", [])
                if isinstance(repo, dict) and "full_name" in repo
            ]
            affected = await service.process_github_installation_repositories(
                action=action,
                github_installation_id=installation_id,
                repositories_added=repos_added,
                repositories_removed=repos_removed,
                correlation_id=correlation_id,
            )
            affected_count = len(affected)

    elif event_type == "installation":
        action = payload.get("action", "")
        installation = payload.get("installation", {})
        installation_id = installation.get("id")
        if isinstance(installation_id, int):
            repos = [
                repo["full_name"]
                for repo in payload.get("repositories", [])
                if isinstance(repo, dict) and "full_name" in repo
            ]
            affected = await service.process_github_installation(
                action=action,
                github_installation_id=installation_id,
                repositories=repos,
                correlation_id=correlation_id,
            )
            affected_count = len(affected)

    response_body = {"status": "ok", "event": event_type, "affected_projects": affected_count}
    if reservation is not None:
        await idempotency.complete(
            reservation, status_code=status.HTTP_200_OK, response_body=response_body
        )
    await session.commit()
    return JSONResponse(status_code=status.HTTP_200_OK, content=response_body)
