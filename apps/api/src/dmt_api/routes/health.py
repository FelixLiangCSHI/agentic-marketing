"""Health endpoints.

``/live`` only checks that the process answers. ``/ready`` checks local
configuration; it must never call paid or external APIs.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from dmt_api.errors import error_response
from dmt_api.settings import Settings

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "live"}


@router.get("/ready")
def ready() -> JSONResponse:
    settings = Settings.from_env()
    if not settings.is_ready:
        return error_response(
            503,
            "not_ready",
            "configuration is invalid",
            retryable=True,
            details={"problems": list(settings.problems)},
        )
    return JSONResponse(
        status_code=200,
        content={
            "status": "ready",
            "checks": {
                "config": "ok",
                "mode": settings.mode,
                "environment": settings.environment,
            },
        },
    )
