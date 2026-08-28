"""FastAPI application factory for the Control API skeleton."""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from dmt_api import __version__
from dmt_api.errors import error_response
from dmt_api.identity.auth import ForbiddenError, UnauthenticatedError
from dmt_api.identity.provider import IdentityProvider
from dmt_api.routes import approvals, content, health, me, reviews, runs, tasks
from dmt_api.routes.approvals import PersistenceUnavailableError


def create_app(
    *,
    identity_provider: IdentityProvider | None = None,
    database_url: str | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Agentic Marketing Control API",
        version=__version__,
        docs_url=None,
        redoc_url=None,
    )
    app.state.identity_provider = identity_provider
    app.state.database_url = database_url or os.environ.get("DMT_DATABASE_URL")
    app.include_router(health.router)
    app.include_router(me.router)
    app.include_router(runs.router)
    app.include_router(tasks.router)
    app.include_router(approvals.router)
    app.include_router(content.router)
    app.include_router(reviews.router)

    @app.exception_handler(UnauthenticatedError)
    async def unauthenticated_handler(
        request: Request, exc: UnauthenticatedError
    ) -> JSONResponse:
        # Never echo the credential; the message only describes the failure.
        return error_response(
            401, "unauthenticated", "authentication is required", retryable=False
        )

    @app.exception_handler(ForbiddenError)
    async def forbidden_handler(request: Request, exc: ForbiddenError) -> JSONResponse:
        return error_response(403, "forbidden", str(exc), retryable=False)

    @app.exception_handler(PersistenceUnavailableError)
    async def persistence_unavailable_handler(
        request: Request, exc: PersistenceUnavailableError
    ) -> JSONResponse:
        return error_response(
            503,
            "persistence_unavailable",
            "no database is configured for this process",
            retryable=True,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return error_response(
            422,
            "validation_error",
            "request does not match the typed contract",
            retryable=False,
            details={
                "errors": [
                    {
                        "loc": "/".join(str(part) for part in error["loc"]),
                        "msg": str(error["msg"]),
                    }
                    for error in exc.errors()
                ]
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        # Never leak stack traces, secrets or vendor tokens to clients.
        return error_response(
            500,
            "internal_error",
            "an unexpected error occurred",
            retryable=True,
        )

    return app


app = create_app()
