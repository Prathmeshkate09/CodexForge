from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Request

from app.core.security import (
    issue_development_token,
    verify_development_identity_secret,
)
from app.schemas.auth import DevelopmentTokenRequest, TokenResponse

router = APIRouter()


@router.post("/dev/token", response_model=TokenResponse, include_in_schema=False)
async def issue_dev_token(
    payload: DevelopmentTokenRequest,
    request: Request,
    x_dev_identity_key: Annotated[str | None, Header()] = None,
) -> TokenResponse:
    settings = request.app.state.settings
    verify_development_identity_secret(settings, x_dev_identity_key)
    token = issue_development_token(
        settings,
        subject=payload.subject,
        email=payload.email,
        name=payload.name,
        scopes=payload.scopes,
    )
    return TokenResponse(access_token=token)
