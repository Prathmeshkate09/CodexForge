from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """An expected API error whose public detail is safe to return."""

    def __init__(
        self,
        code: str,
        detail: str,
        *,
        status_code: int = 400,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status_code = status_code
        self.headers = headers or {}


class AuthorizationError(AppError):
    def __init__(self, detail: str = "Authentication is required.") -> None:
        super().__init__(
            "unauthorized",
            detail,
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenError(AppError):
    def __init__(self, detail: str = "You are not allowed to perform this action.") -> None:
        super().__init__("forbidden", detail, status_code=403)


class NotFoundError(AppError):
    def __init__(self, detail: str = "The requested resource was not found.") -> None:
        super().__init__("not_found", detail, status_code=404)


class ConflictError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__("conflict", detail, status_code=409)


class RateLimitError(AppError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            "rate_limited",
            "Too many requests. Try again later.",
            status_code=429,
            headers={"Retry-After": str(retry_after_seconds)},
        )


class ServiceUnavailableError(AppError):
    def __init__(self, detail: str = "The service is temporarily unavailable.") -> None:
        super().__init__("service_unavailable", detail, status_code=503)


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):
        return await unhandled_error_handler(request, exc)
    request_state = getattr(request, "state", None)
    correlation_id = getattr(request_state, "correlation_id", None)
    content: dict[str, Any] = {
        "detail": exc.detail,
        "error": {"code": exc.code, "message": exc.detail},
    }
    if correlation_id:
        content["request_id"] = correlation_id
    headers = {**exc.headers}
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id
        headers["X-Request-ID"] = correlation_id
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=headers,
    )


async def unhandled_error_handler(request: Request, _: Exception) -> JSONResponse:
    """Never expose stack traces or database/provider details to an API caller."""

    correlation_id = getattr(request.state, "correlation_id", None)
    payload: dict[str, Any] = {
        "error": {"code": "internal_error", "message": "An unexpected error occurred."}
    }
    if correlation_id:
        payload["error"]["correlation_id"] = correlation_id
        payload["request_id"] = correlation_id
    payload["detail"] = "An unexpected error occurred."
    headers = {}
    if correlation_id:
        headers = {"X-Correlation-ID": correlation_id, "X-Request-ID": correlation_id}
    return JSONResponse(status_code=500, content=payload, headers=headers)
