from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AuthorizationError, RateLimitError
from app.core.security import JwtVerifier, Principal
from app.db.session import Database
from app.services.rate_limit import RateLimiter

oauth2_bearer = HTTPBearer(
    scheme_name="OAuth2BearerJWT",
    bearerFormat="JWT",
    description="OAuth2 access token issued by the configured identity provider.",
    auto_error=False,
)


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    database: Database = request.app.state.database
    async for session in database.session():
        yield session


async def get_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(oauth2_bearer)],
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthorizationError()
    settings = get_app_settings(request)
    return await JwtVerifier(settings).verify(credentials.credentials)


async def get_rate_limited_principal(
    request: Request,
    principal: Annotated[Principal, Depends(get_principal)],
) -> Principal:
    settings = get_app_settings(request)
    limiter: RateLimiter = request.app.state.rate_limiter
    user_result = await limiter.check(
        f"user:{principal.subject}",
        limit=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    if not user_result.allowed:
        raise RateLimitError(user_result.retry_after_seconds)
    return principal


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
PrincipalDep = Annotated[Principal, Depends(get_rate_limited_principal)]
