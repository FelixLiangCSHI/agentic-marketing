"""Health endpoints.

``/live`` only checks that the process answers. ``/ready`` checks local
configuration; it must never call paid or external APIs.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from dmt_api.errors import error_response
from dmt_api.persistence.db import get_engine
from dmt_api.settings import Settings

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "live"}


@router.get("/ready")
def ready(request: Request) -> JSONResponse:
    settings = Settings.from_env()
    checks = {
        "config": "ok",
        "mode": settings.mode,
        "environment": settings.environment,
        "database": "not_configured",
        "identity_provider": (
            "configured"
            if getattr(request.app.state, "identity_provider", None) is not None
            else "not_configured"
        ),
    }
    if not settings.is_ready:
        return error_response(
            503,
            "not_ready",
            "configuration is invalid",
            retryable=True,
            details={"problems": list(settings.problems)},
        )
    database_url = getattr(request.app.state, "database_url", None)
    if database_url:
        try:
            engine = get_engine(request.app)
            if engine is None:
                raise SQLAlchemyError("database engine unavailable")
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except SQLAlchemyError:
            checks["database"] = "unavailable"
            return error_response(
                503,
                "not_ready",
                "local dependency check failed",
                retryable=True,
                details={"checks": checks},
            )
    return JSONResponse(
        status_code=200,
        content={
            "status": "ready",
            "checks": checks,
        },
    )
