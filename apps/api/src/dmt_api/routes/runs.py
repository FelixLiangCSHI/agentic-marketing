"""Typed placeholder routes for runs.

These endpoints validate their inputs against the v1 contracts but do not
fake success: every call answers with the versioned ``not_implemented``
error until the persistence layer lands (Subphase 03+).
"""

from __future__ import annotations

from fastapi import APIRouter, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from dmt_api.contracts import (
    ID_PATTERN,
    AgentType,
    Identifier,
    Name,
    SemVer,
)
from dmt_api.errors import not_implemented

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


class RunCreateRequest(BaseModel):
    """Typed create payload; unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid", strict=True)

    agent_type: AgentType
    workflow_name: Name
    workflow_version: SemVer
    tenant: Identifier
    business_unit: Identifier
    requester_id: Identifier


@router.post("")
def create_run(request: RunCreateRequest) -> JSONResponse:
    return not_implemented("runs.create")


@router.get("/{run_id}")
def get_run(run_id: str = Path(pattern=ID_PATTERN)) -> JSONResponse:
    return not_implemented("runs.get")


@router.post("/{run_id}/cancel")
def cancel_run(run_id: str = Path(pattern=ID_PATTERN)) -> JSONResponse:
    return not_implemented("runs.cancel")
