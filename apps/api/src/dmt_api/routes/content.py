"""Content request input validation routes (Phase 02 / Subphase 01).

The request body is validated against the frozen ``content-request.v1``
contract (see ``packages/domain-contracts/schemas/``). Free text fields are
untrusted data: shape-validated only, never executed. No campaign account,
budget or channel write credential fields exist on this boundary.

Valid input never fakes success: the workflow lands in a later subphase, so
these endpoints answer with the versioned ``not_implemented`` error.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path
from fastapi.responses import JSONResponse

from dmt_api.contracts import ID_PATTERN, ContentRequestV1
from dmt_api.errors import not_implemented
from dmt_api.identity.auth import require_roles
from dmt_api.identity.provider import Principal
from dmt_api.identity.roles import Role

router = APIRouter(prefix="/api/v1/content", tags=["content"])

_CONTENT_CREATOR = require_roles({Role.CONTENT_CREATOR})
_CONTENT_VIEWER = require_roles(set(Role))


@router.post("/requests")
def create_content_request(
    request: ContentRequestV1,
    _principal: Principal = Depends(_CONTENT_CREATOR),
) -> JSONResponse:
    return not_implemented("content.requests.create")


@router.get("/requests/{request_id}")
def get_content_request(
    request_id: str = Path(pattern=ID_PATTERN),
    _principal: Principal = Depends(_CONTENT_VIEWER),
) -> JSONResponse:
    return not_implemented("content.requests.get")
