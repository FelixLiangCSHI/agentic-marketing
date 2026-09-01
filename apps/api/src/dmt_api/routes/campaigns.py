"""Campaign API placeholder (Phase 03 / Subphase 01).

Only the contract surface exists here: draft creation is validated against
``campaign-proposal.v1`` inputs by the ``packages/campaign-draft`` builder,
but the persistence/worker wiring belongs to later subphases, so every
endpoint answers ``501 not_implemented``. No channel API, credential or
external side effect is reachable from this router.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from dmt_api.errors import error_response

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])


@router.post("/proposals")
def create_proposal_draft() -> JSONResponse:
    return error_response(
        501,
        "not_implemented",
        "campaign proposal drafting is wired in Phase 03 / Subphase 05; "
        "use packages/campaign-draft for the authoritative builder",
        retryable=False,
    )


@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: str) -> JSONResponse:
    return error_response(
        501,
        "not_implemented",
        "campaign proposal lookup is wired in Phase 03 / Subphase 05",
        retryable=False,
    )
