"""Versioned API error envelope.

Every non-2xx response uses this structure. Stack traces, secrets and raw
vendor tokens must never appear in responses.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict


class ApiError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    trace_id: str
    retryable: bool
    details: dict[str, Any] | None = None


def new_trace_id() -> str:
    return uuid.uuid4().hex


def error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    retryable: bool,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    body = ApiError(
        code=code,
        message=message,
        trace_id=new_trace_id(),
        retryable=retryable,
        details=details,
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())


def not_implemented(feature: str) -> JSONResponse:
    """Typed placeholder response: never fakes success."""
    return error_response(
        501,
        "not_implemented",
        f"{feature} is not implemented in Phase 01 / Subphase 02",
        retryable=False,
        details={"feature": feature},
    )
