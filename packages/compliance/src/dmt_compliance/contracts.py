"""Versioned compliance contracts (Phase 02 / Subphase 06).

Structured issue output per the parent plan:
``compliance_result_id, content_version_id, policy_version, issues[],
severity, rule_id, claim_id, source_reference, suggested_rework_node,
automated_status, reviewer_status``.

The automated status is decided by deterministic rules only. The Critic
contributes *questions*, never verdicts — a rule failure can never be
turned into a pass by any model output. Human review status lives in the
Control API, not here.
"""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr

Severity = Literal["critical", "major", "minor"]
ReworkNode = Literal["fact_issue", "copy_issue", "asset_issue"]
AutomatedStatus = Literal["PASS", "BLOCKED"]
ReviewerStatus = Literal["PENDING", "APPROVED", "REJECTED", "INVALIDATED"]

_ID = Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"


class SourceReferenceV1(_Model):
    """Pointer to the approved source a claim cites (or lacks)."""

    source_id: StrictStr | None
    source_version: StrictStr | None
    source_content_hash: StrictStr | None
    market: StrictStr | None
    expires_at: StrictStr | None


class ComplianceIssueV1(_Model):
    """One deterministic rule finding, bound to a claim and a rework node."""

    issue_id: _ID
    rule_id: Annotated[StrictStr, Field(pattern=r"^R-[A-Z]{2,8}-\d{3}$")]
    claim_id: StrictStr | None
    severity: Severity
    detail: Annotated[StrictStr, Field(min_length=1, max_length=2000)]
    source_reference: SourceReferenceV1 | None
    suggested_rework_node: ReworkNode


class CriticQuestionV1(_Model):
    """Critic output: a question for human reviewers, never a verdict."""

    question_id: _ID
    claim_id: StrictStr | None
    category: Literal[
        "ambiguity", "exaggeration", "competitor_comparison", "citation_mismatch"
    ]
    question: Annotated[StrictStr, Field(min_length=1, max_length=2000)]


class ComplianceResultV1(_Model):
    """Structured, versioned compliance result for one content version."""

    compliance_result_id: _ID
    content_version_id: StrictStr
    policy_version: StrictStr
    issues: tuple[ComplianceIssueV1, ...]
    critic_questions: tuple[CriticQuestionV1, ...]
    checked_rules: tuple[StrictStr, ...]
    automated_status: AutomatedStatus
    reviewer_status: ReviewerStatus

    def result_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def claim_id_for(text: str) -> str:
    """Deterministic claim ID from the claim text."""
    return "claim-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def content_version_id_for(*hashes: str) -> str:
    """Deterministic content version ID binding copy + media hashes."""
    joined = "|".join(hashes)
    return "cv-" + hashlib.sha256(joined.encode("utf-8")).hexdigest()[:24]
