"""Versioned node input/output contracts for the Content Workflow.

Every workflow node consumes and produces one of these frozen, versioned
models; each transition is journaled with the schema version and content
hash. Free text (objective, prompt, copy body) is untrusted data.

These are package-internal runtime contracts (like ``ProductRecord`` in
product-rag); cross-language freezing into ``domain-contracts`` happens
when the API layer exposes them (left for the API wiring).
"""

from __future__ import annotations

import hashlib
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from content_workflow.skills import Channel
from product_rag.citations import Citation
from product_rag.models import (
    DateTimeUtc,
    Identifier,
    Locale,
    Market,
    Sha256Hash,
)

MediaType = Literal["image"]
ReworkTarget = Literal["fact_issue", "copy_issue", "asset_issue"]
ReviewOutcome = Literal["approved", "rejected"]

CONTENT_WORKFLOW_VERSION = "content-workflow/1.0.0"


class _NodeModel(BaseModel):
    # strict=False（仅此层）：LangGraph Checkpoint 恢复时通过
    # ``cls(**model_dump())`` 重建模型，tuple/嵌套模型以 list/dict 形式
    # 回传，需要宽松校验才能完整重新验证（而非退化为未验证的
    # ``model_construct``）。字段仍然 frozen 且禁止未知字段。
    model_config = ConfigDict(extra="forbid", strict=False, frozen=True)

    schema_version: Literal["1.0"] = "1.0"


def model_hash(model: BaseModel) -> str:
    """Deterministic content hash of a node artifact for the journal."""
    payload = model.model_dump_json(exclude_none=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


class WorkflowRequestV1(_NodeModel):
    """Validated Content Workflow input (mirror of content-request.v1
    fields the workflow needs; the API layer owns the full contract)."""

    request_id: Identifier
    tenant: Identifier
    product_ids: Annotated[tuple[Identifier, ...], Field(min_length=1, max_length=16)]
    market: Market
    locale: Locale
    channel: Channel
    objective: Annotated[StrictStr, Field(min_length=1, max_length=2000)]
    target_audience: Annotated[
        tuple[Annotated[StrictStr, Field(min_length=1, max_length=200)], ...],
        Field(min_length=1, max_length=16),
    ]
    requested_media_types: tuple[MediaType, ...]
    as_of: DateTimeUtc


class RetrievedFactV1(_NodeModel):
    """One approved passage with its index-built citation."""

    text: StrictStr
    score: float
    citation: Citation


class FactBundleV1(_NodeModel):
    """Output of RetrieveProductFacts; only cited approved facts."""

    request_id: Identifier
    index_version: StrictStr
    facts: tuple[RetrievedFactV1, ...]


class ContentBriefV1(_NodeModel):
    """Output of BuildBrief: facts, banned claims, disclosures, tone,
    channel constraints and skill versions — all deterministic."""

    request_id: Identifier
    tenant: Identifier
    market: Market
    locale: Locale
    channel: Channel
    objective: StrictStr
    target_audience: tuple[StrictStr, ...]
    tone: StrictStr
    facts: tuple[RetrievedFactV1, ...]
    banned_phrases: tuple[StrictStr, ...]
    required_disclosures: tuple[StrictStr, ...]
    max_headline_chars: int
    skill_versions: tuple[tuple[StrictStr, StrictStr], ...]


class CopyClaimV1(_NodeModel):
    """A claim in generated copy; citation is None only when the model
    failed to ground it — compliance flags and blocks such claims."""

    text: Annotated[StrictStr, Field(min_length=1, max_length=4000)]
    citation: Citation | None


class CopyDraftV1(_NodeModel):
    """Output of GenerateCopy (fake model): structured draft."""

    request_id: Identifier
    channel: Channel
    headline: Annotated[StrictStr, Field(min_length=1, max_length=400)]
    body: Annotated[StrictStr, Field(min_length=1, max_length=8000)]
    claims: tuple[CopyClaimV1, ...]
    disclosures: tuple[StrictStr, ...]
    model_id: StrictStr


class MediaAssetV1(_NodeModel):
    """Output of GenerateMedia (fake media): reference only, no binary."""

    request_id: Identifier
    asset_id: Identifier
    media_type: MediaType
    uri: StrictStr
    sha256: Sha256Hash
    alt_text: StrictStr
    generator_id: StrictStr


class ComplianceViolationV1(_NodeModel):
    rule: StrictStr
    detail: StrictStr


class ComplianceReportV1(_NodeModel):
    """Output of ComplianceCheck: deterministic hard rules only.

    This is a machine gate, not a Medical Approval; human review remains
    mandatory downstream.
    """

    request_id: Identifier
    passed: bool
    violations: tuple[ComplianceViolationV1, ...]
    uncited_claims: tuple[StrictStr, ...]
    checked_rules: tuple[StrictStr, ...]


class ReviewDecisionV1(_NodeModel):
    """Human review decision (fake reviewer in repo/CI)."""

    request_id: Identifier
    reviewer_id: Identifier
    outcome: ReviewOutcome
    rework_target: ReworkTarget | None
    notes: Annotated[StrictStr, Field(max_length=4000)]


class ApprovedPackageV1(_NodeModel):
    """Final package; only assembled after human approval with all skills
    formally APPROVED. Otherwise the run ends as DRAFT."""

    request_id: Identifier
    tenant: Identifier
    market: Market
    locale: Locale
    channel: Channel
    copy_hash: Sha256Hash
    media_hashes: tuple[Sha256Hash, ...]
    compliance_report_hash: Sha256Hash
    review_decision_hash: Sha256Hash
    skill_versions: tuple[tuple[StrictStr, StrictStr], ...]
    workflow_version: StrictStr
