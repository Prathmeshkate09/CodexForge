from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.api.v1.routes.health import health
from app.core.config import Settings, get_settings
from app.core.errors import AppError, app_error_handler, unhandled_error_handler
from app.core.logging import configure_logging, correlation_id_middleware
from app.db.session import Database
from app.services.rate_limit import build_rate_limiter


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            rate_limiter = app.state.rate_limiter
            close = getattr(rate_limiter, "close", None)
            if close is not None:
                await close()
            await app.state.database.dispose()

    configure_logging()
    app = FastAPI(title=settings.api_name, version=settings.api_version, lifespan=lifespan)
    app.state.settings = settings
    app.state.database = Database(settings.database_url)
    app.state.rate_limiter = build_rate_limiter(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Correlation-ID",
        ],
        expose_headers=["X-Request-ID", "X-Correlation-ID", "Retry-After"],
        max_age=600,
    )
    app.middleware("http")(correlation_id_middleware)
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
    app.include_router(api_router)
    app.get("/health", include_in_schema=False)(health)
    return app


app = create_app()
