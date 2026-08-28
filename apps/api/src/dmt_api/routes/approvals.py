"""Typed placeholder routes for approvals (no fake success)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from dmt_api.errors import not_implemented

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


@router.get("")
def list_approvals() -> JSONResponse:
    return not_implemented("approvals.list")
