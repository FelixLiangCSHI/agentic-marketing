"""FastAPI application factory for the Control API skeleton."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from dmt_api import __version__
from dmt_api.errors import error_response
from dmt_api.routes import approvals, health, runs, tasks


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agentic Marketing Control API",
        version=__version__,
        docs_url=None,
        redoc_url=None,
    )
    app.include_router(health.router)
    app.include_router(runs.router)
    app.include_router(tasks.router)
    app.include_router(approvals.router)

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
