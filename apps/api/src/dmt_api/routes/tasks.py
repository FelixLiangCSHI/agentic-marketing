"""Typed placeholder routes for tasks (no fake success)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from dmt_api.errors import not_implemented

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.get("")
def list_tasks() -> JSONResponse:
    return not_implemented("tasks.list")
