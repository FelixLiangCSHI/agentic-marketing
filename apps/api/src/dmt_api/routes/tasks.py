"""Typed placeholder routes for tasks (no fake success)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from dmt_api.errors import not_implemented
from dmt_api.identity.auth import require_roles
from dmt_api.identity.provider import Principal
from dmt_api.identity.roles import Role

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

_TASK_VIEWER = require_roles({Role.ADMIN, Role.AUDITOR, Role.CAMPAIGN_OPERATOR})


@router.get("")
def list_tasks(_principal: Principal = Depends(_TASK_VIEWER)) -> JSONResponse:
    return not_implemented("tasks.list")
