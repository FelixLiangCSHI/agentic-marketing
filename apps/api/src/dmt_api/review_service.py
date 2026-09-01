"""Two-track human review (Medical + Marketing) over compliance results.

Server-side guarantees (never trusting the client):
* The review track is derived from the principal's server-resolved roles,
  never from a client-supplied field.
* Every decision binds to the exact artifact hash; a stale hash is a
  typed conflict, not a silent success.
* Separation of duties: the creator cannot review, and one identity can
  never decide both tracks.
* Approval is impossible while the deterministic compliance gate says
  BLOCKED — no human can override a rule failure through this API.
* A content change invalidates all prior approvals for the case.

The store is in-memory and injectable (same posture as the approval
service tests): persistence wiring is deferred, semantics are real.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

from dmt_api.identity.provider import Principal
from dmt_api.identity.roles import Role


class ReviewTrack(str, Enum):
    MEDICAL = "medical"
    MARKETING = "marketing"


#: Server-controlled mapping from role to the review track it may decide.
TRACK_FOR_ROLE: dict[Role, ReviewTrack] = {
    Role.MEDICAL_REVIEWER: ReviewTrack.MEDICAL,
    Role.MARKETING_REVIEWER: ReviewTrack.MARKETING,
}

VALID_REWORK_TARGETS: frozenset[str] = frozenset(
    {"fact_issue", "copy_issue", "asset_issue"}
)


class ReviewError(Exception):
    """Base class for typed review failures."""


class ReviewNotFoundError(ReviewError):
    pass


class StaleArtifactError(ReviewError):
    """Decision was made against an outdated content version."""


class SeparationOfDutiesError(ReviewError):
    pass


class RoleNotAllowedError(ReviewError):
    pass


class IllegalReviewStateError(ReviewError):
    pass


class InvalidDecisionError(ReviewError):
    """Reject without reason/target, or approve against a BLOCKED gate."""


@dataclass(frozen=True)
class TrackDecision:
    status: str = "PENDING"  # PENDING | APPROVED | REJECTED | INVALIDATED
    decided_by: str | None = None
    decided_at: datetime | None = None
    reason: str | None = None
    rework_target: str | None = None


@dataclass(frozen=True)
class ReviewCase:
    review_id: str
    run_id: str
    tenant: str
    created_by: str
    created_at: datetime
    artifact_hash: str
    policy_version: str
    workflow_version: str
    automated_status: str  # PASS | BLOCKED (deterministic gate outcome)
    content: dict[str, object]
    issues: tuple[dict[str, object], ...]
    critic_questions: tuple[dict[str, object], ...]
    sources: tuple[dict[str, object], ...]
    medical: TrackDecision = field(default_factory=TrackDecision)
    marketing: TrackDecision = field(default_factory=TrackDecision)
    revision: int = 1

    @property
    def status(self) -> str:
        tracks = (self.medical, self.marketing)
        if any(t.status == "REJECTED" for t in tracks):
            return "REJECTED"
        if all(t.status == "APPROVED" for t in tracks):
            return "APPROVED"
        return "AWAITING_REVIEW"

    def track(self, track: ReviewTrack) -> TrackDecision:
        return self.medical if track is ReviewTrack.MEDICAL else self.marketing


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReviewService:
    """In-memory review store with server-side authority checks."""

    def __init__(self, *, clock: Callable[[], datetime] = _utcnow) -> None:
        self._clock = clock
        self._cases: dict[str, ReviewCase] = {}

    def create(
        self,
        *,
        principal: Principal,
        run_id: str,
        tenant: str,
        artifact_hash: str,
        policy_version: str,
        workflow_version: str,
        automated_status: str,
        content: dict[str, object],
        issues: tuple[dict[str, object], ...],
        critic_questions: tuple[dict[str, object], ...],
        sources: tuple[dict[str, object], ...],
    ) -> ReviewCase:
        review_id = f"rev-{secrets.token_hex(8)}"
        case = ReviewCase(
            review_id=review_id,
            run_id=run_id,
            tenant=tenant,
            created_by=principal.subject,
            created_at=self._clock(),
            artifact_hash=artifact_hash,
            policy_version=policy_version,
            workflow_version=workflow_version,
            automated_status=automated_status,
            content=content,
            issues=issues,
            critic_questions=critic_questions,
            sources=sources,
        )
        self._cases[review_id] = case
        return case

    def get(self, review_id: str, *, tenant: str | None = None) -> ReviewCase:
        case = self._cases.get(review_id)
        if case is None or (tenant is not None and case.tenant != tenant):
            raise ReviewNotFoundError(review_id)
        return case

    def list_cases(self, *, tenant: str | None = None) -> tuple[ReviewCase, ...]:
        return tuple(
            sorted(
                (
                    case
                    for case in self._cases.values()
                    if tenant is None or case.tenant == tenant
                ),
                key=lambda c: c.created_at,
                reverse=True,
            )
        )

    def decide(
        self,
        *,
        review_id: str,
        principal: Principal,
        artifact_hash: str,
        decision: str,
        reason: str | None,
        rework_target: str | None,
    ) -> ReviewCase:
        case = self.get(review_id, tenant=principal.tenant)

        # Track is derived from server-resolved roles only.
        tracks = sorted(
            {
                TRACK_FOR_ROLE[role]
                for role in principal.roles
                if role in TRACK_FOR_ROLE
            },
            key=lambda t: t.value,
        )
        if not tracks:
            raise RoleNotAllowedError("principal holds no reviewer role")
        track = tracks[0]

        if principal.subject == case.created_by:
            raise SeparationOfDutiesError("creator cannot review own content")
        other = case.track(
            ReviewTrack.MARKETING if track is ReviewTrack.MEDICAL else ReviewTrack.MEDICAL
        )
        if other.decided_by == principal.subject:
            raise SeparationOfDutiesError(
                "the same identity cannot decide both review tracks"
            )

        if artifact_hash != case.artifact_hash:
            raise StaleArtifactError(
                "decision references an outdated content version"
            )
        if case.track(track).status not in {"PENDING", "INVALIDATED"}:
            raise IllegalReviewStateError(
                f"{track.value} track is already decided"
            )

        if decision == "approved":
            if case.automated_status == "BLOCKED":
                raise InvalidDecisionError(
                    "compliance rules block this content; approval is not possible"
                )
        elif decision == "rejected":
            if not reason or not reason.strip():
                raise InvalidDecisionError("rejection requires a reason")
            if rework_target not in VALID_REWORK_TARGETS:
                raise InvalidDecisionError(
                    "rejection requires a valid rework target node"
                )
        else:
            raise InvalidDecisionError(f"unknown decision: {decision}")

        decided = TrackDecision(
            status="APPROVED" if decision == "approved" else "REJECTED",
            decided_by=principal.subject,
            decided_at=self._clock(),
            reason=reason,
            rework_target=rework_target if decision == "rejected" else None,
        )
        updated = replace(
            case,
            medical=decided if track is ReviewTrack.MEDICAL else case.medical,
            marketing=decided if track is ReviewTrack.MARKETING else case.marketing,
        )
        self._cases[review_id] = updated
        return updated

    def content_changed(
        self,
        *,
        review_id: str,
        principal: Principal,
        new_artifact_hash: str,
        automated_status: str,
        content: dict[str, object],
        issues: tuple[dict[str, object], ...],
        critic_questions: tuple[dict[str, object], ...],
    ) -> ReviewCase:
        case = self.get(review_id, tenant=principal.tenant)
        if principal.subject != case.created_by:
            raise RoleNotAllowedError(
                "only the creator can register a content change"
            )

        def _invalidate(track: TrackDecision) -> TrackDecision:
            if track.status == "APPROVED":
                return replace(track, status="INVALIDATED")
            if track.status == "REJECTED":
                # A rejection stays on record; the new revision reopens review.
                return TrackDecision()
            return track

        updated = replace(
            case,
            artifact_hash=new_artifact_hash,
            automated_status=automated_status,
            content=content,
            issues=issues,
            critic_questions=critic_questions,
            medical=_invalidate(case.medical),
            marketing=_invalidate(case.marketing),
            revision=case.revision + 1,
        )
        self._cases[review_id] = updated
        return updated
