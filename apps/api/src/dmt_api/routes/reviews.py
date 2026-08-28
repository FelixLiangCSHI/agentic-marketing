"""Review API: create, list, side-by-side detail, decide, content-changed.

Medical/Marketing tracks are resolved from server-side roles only; every
decision binds to the artifact hash; rule failures (BLOCKED) can never be
approved through this API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Path, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from dmt_api.contracts import ID_PATTERN, Identifier, SemVer, Sha256Hash
from dmt_api.errors import error_response
from dmt_api.identity.provider import Principal
from dmt_api.identity.auth import require_roles
from dmt_api.identity.roles import Role
from dmt_api.review_service import (
    IllegalReviewStateError,
    InvalidDecisionError,
    ReviewCase,
    ReviewNotFoundError,
    ReviewService,
    RoleNotAllowedError,
    SeparationOfDutiesError,
    StaleArtifactError,
    TrackDecision,
)

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])

_CREATOR = require_roles({Role.CONTENT_CREATOR})
_REVIEWER = require_roles({Role.MEDICAL_REVIEWER, Role.MARKETING_REVIEWER})
_VIEWER = require_roles(set(Role))


def get_review_service(request: Request) -> ReviewService:
    service = getattr(request.app.state, "review_service", None)
    if not isinstance(service, ReviewService):
        service = ReviewService()
        request.app.state.review_service = service
    return service


class ReviewCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: Identifier
    tenant: Identifier
    artifact_hash: Sha256Hash
    policy_version: SemVer
    workflow_version: SemVer
    automated_status: Literal["PASS", "BLOCKED"]
    content: dict[str, object] = Field(default_factory=dict)
    issues: tuple[dict[str, object], ...] = ()
    critic_questions: tuple[dict[str, object], ...] = ()
    sources: tuple[dict[str, object], ...] = ()


class ReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_hash: Sha256Hash
    decision: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, max_length=2000)
    rework_target: Literal["fact_issue", "copy_issue", "asset_issue"] | None = None


class ContentChangedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_hash: Sha256Hash
    automated_status: Literal["PASS", "BLOCKED"]
    content: dict[str, object] = Field(default_factory=dict)
    issues: tuple[dict[str, object], ...] = ()
    critic_questions: tuple[dict[str, object], ...] = ()


class TrackView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    decided_by: str | None
    decided_at: datetime | None
    reason: str | None
    rework_target: str | None


class ReviewView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    run_id: str
    tenant: str
    status: str
    revision: int
    created_by: str
    created_at: datetime
    artifact_hash: str
    policy_version: str
    workflow_version: str
    automated_status: str
    medical: TrackView
    marketing: TrackView


class ReviewDetailView(ReviewView):
    content: dict[str, object]
    issues: tuple[dict[str, object], ...]
    critic_questions: tuple[dict[str, object], ...]
    sources: tuple[dict[str, object], ...]


def _track_view(track: TrackDecision) -> TrackView:
    return TrackView(
        status=track.status,
        decided_by=track.decided_by,
        decided_at=track.decided_at,
        reason=track.reason,
        rework_target=track.rework_target,
    )


def _view(case: ReviewCase) -> ReviewView:
    return ReviewView(
        review_id=case.review_id,
        run_id=case.run_id,
        tenant=case.tenant,
        status=case.status,
        revision=case.revision,
        created_by=case.created_by,
        created_at=case.created_at,
        artifact_hash=case.artifact_hash,
        policy_version=case.policy_version,
        workflow_version=case.workflow_version,
        automated_status=case.automated_status,
        medical=_track_view(case.medical),
        marketing=_track_view(case.marketing),
    )


def _detail(case: ReviewCase) -> ReviewDetailView:
    return ReviewDetailView(
        **_view(case).model_dump(),
        content=case.content,
        issues=case.issues,
        critic_questions=case.critic_questions,
        sources=case.sources,
    )


@router.post("", status_code=201, response_model=ReviewView)
def create_review(
    payload: ReviewCreateRequest,
    principal: Principal = Depends(_CREATOR),
    service: ReviewService = Depends(get_review_service),
) -> ReviewView:
    case = service.create(
        principal=principal,
        run_id=payload.run_id,
        tenant=payload.tenant,
        artifact_hash=payload.artifact_hash,
        policy_version=payload.policy_version,
        workflow_version=payload.workflow_version,
        automated_status=payload.automated_status,
        content=payload.content,
        issues=payload.issues,
        critic_questions=payload.critic_questions,
        sources=payload.sources,
    )
    return _view(case)


@router.get("", response_model=tuple[ReviewView, ...])
def list_reviews(
    principal: Principal = Depends(_VIEWER),
    service: ReviewService = Depends(get_review_service),
) -> tuple[ReviewView, ...]:
    return tuple(_view(case) for case in service.list_cases())


@router.get("/{review_id}", response_model=None)
def get_review(
    review_id: str = Path(pattern=r"^rev-[a-f0-9]{16}$"),
    principal: Principal = Depends(_VIEWER),
    service: ReviewService = Depends(get_review_service),
) -> ReviewDetailView | JSONResponse:
    try:
        case = service.get(review_id)
    except ReviewNotFoundError:
        return error_response(404, "not_found", "review not found", retryable=False)
    return _detail(case)


@router.post("/{review_id}/decision", response_model=None)
def decide_review(
    payload: ReviewDecisionRequest,
    review_id: str = Path(pattern=r"^rev-[a-f0-9]{16}$"),
    principal: Principal = Depends(_REVIEWER),
    service: ReviewService = Depends(get_review_service),
) -> ReviewView | JSONResponse:
    try:
        case = service.decide(
            review_id=review_id,
            principal=principal,
            artifact_hash=payload.artifact_hash,
            decision=payload.decision,
            reason=payload.reason,
            rework_target=payload.rework_target,
        )
    except ReviewNotFoundError:
        return error_response(404, "not_found", "review not found", retryable=False)
    except StaleArtifactError as exc:
        return error_response(409, "stale_artifact", str(exc), retryable=False)
    except SeparationOfDutiesError as exc:
        return error_response(403, "separation_of_duties", str(exc), retryable=False)
    except RoleNotAllowedError as exc:
        return error_response(403, "role_not_allowed", str(exc), retryable=False)
    except IllegalReviewStateError as exc:
        return error_response(409, "illegal_state", str(exc), retryable=False)
    except InvalidDecisionError as exc:
        return error_response(422, "invalid_decision", str(exc), retryable=False)
    return _view(case)


@router.post("/{review_id}/content-changed", response_model=None)
def content_changed(
    payload: ContentChangedRequest,
    review_id: str = Path(pattern=r"^rev-[a-f0-9]{16}$"),
    principal: Principal = Depends(_CREATOR),
    service: ReviewService = Depends(get_review_service),
) -> ReviewView | JSONResponse:
    try:
        case = service.content_changed(
            review_id=review_id,
            principal=principal,
            new_artifact_hash=payload.artifact_hash,
            automated_status=payload.automated_status,
            content=payload.content,
            issues=payload.issues,
            critic_questions=payload.critic_questions,
        )
    except ReviewNotFoundError:
        return error_response(404, "not_found", "review not found", retryable=False)
    except RoleNotAllowedError as exc:
        return error_response(403, "role_not_allowed", str(exc), retryable=False)
    return _view(case)
