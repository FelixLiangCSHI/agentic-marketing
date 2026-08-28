"""Content request input validation routes (Phase 02 / Subphase 01).

The request body is validated against the frozen ``content-request.v1``
contract (see ``packages/domain-contracts/schemas/``). Free text fields are
untrusted data: shape-validated only, never executed. No campaign account,
budget or channel write credential fields exist on this boundary.

Valid input never fakes success: the workflow lands in a later subphase, so
these endpoints answer with the versioned ``not_implemented`` error.
"""

from __future__ import annotations

from fastapi import APIRouter, Path
from fastapi.responses import JSONResponse

from dmt_api.contracts import ID_PATTERN, ContentRequestV1
from dmt_api.errors import not_implemented

router = APIRouter(prefix="/api/v1/content", tags=["content"])


@router.post("/requests")
def create_content_request(request: ContentRequestV1) -> JSONResponse:
    return not_implemented("content.requests.create")


@router.get("/requests/{request_id}")
def get_content_request(request_id: str = Path(pattern=ID_PATTERN)) -> JSONResponse:
    return not_implemented("content.requests.get")
