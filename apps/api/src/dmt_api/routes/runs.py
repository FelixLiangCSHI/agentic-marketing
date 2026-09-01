"""Typed placeholder routes for runs.

These endpoints validate their inputs against the v1 contracts but do not
fake success: every call answers with the versioned ``not_implemented``
error until the persistence layer lands (Subphase 03+).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path
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
from dmt_api.identity.auth import require_roles
from dmt_api.identity.provider import Principal
from dmt_api.identity.roles import Role

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])

_RUN_CREATOR = require_roles({Role.CONTENT_CREATOR, Role.CAMPAIGN_OPERATOR})
_RUN_VIEWER = require_roles(set(Role))
_RUN_CANCELLER = require_roles({Role.CAMPAIGN_OPERATOR, Role.ADMIN})


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
def create_run(
    request: RunCreateRequest,
    _principal: Principal = Depends(_RUN_CREATOR),
) -> JSONResponse:
    return not_implemented("runs.create")


@router.get("/{run_id}")
def get_run(
    run_id: str = Path(pattern=ID_PATTERN),
    _principal: Principal = Depends(_RUN_VIEWER),
) -> JSONResponse:
    return not_implemented("runs.get")


@router.post("/{run_id}/cancel")
def cancel_run(
    run_id: str = Path(pattern=ID_PATTERN),
    _principal: Principal = Depends(_RUN_CANCELLER),
) -> JSONResponse:
    return not_implemented("runs.cancel")
