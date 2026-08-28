"""GET /api/v1/me — the server-side verified identity."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from dmt_api.identity.auth import get_principal
from dmt_api.identity.provider import Principal

router = APIRouter(prefix="/api/v1/me", tags=["identity"])


class MeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    display_name: str
    roles: list[str]


@router.get("")
def me(principal: Principal = Depends(get_principal)) -> MeResponse:
    return MeResponse(
        subject=principal.subject,
        display_name=principal.display_name,
        roles=sorted(role.value for role in principal.roles),
    )
