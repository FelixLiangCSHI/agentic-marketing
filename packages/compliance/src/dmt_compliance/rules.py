"""Deterministic compliance rules (layer 1 of the three-layer gate).

Every rule emits structured issues with ``rule_id``, ``claim_id``,
``severity``, ``source_reference`` and ``suggested_rework_node``. Rules are
pure functions of committed policy + content artifacts — no model input can
change their outcome.

Rule registry:
- R-CITE-001  uncited claim                      critical  copy_issue
- R-EXP-002   expired claim source               critical  fact_issue
- R-MKT-003   cross-market claim source          critical  fact_issue
- R-CITE-011  citation not grounded in facts     critical  fact_issue
- R-BAN-004   banned expression                  policy    copy_issue
- R-CMP-005   competitor comparison              major     copy_issue
- R-APR-006   fabricated regulator approval      critical  copy_issue
- R-DIS-007   missing required disclosure        major     copy_issue
- R-LEN-008   headline exceeds channel limit     minor     copy_issue
- R-MED-009   requested media asset missing      major     asset_issue
- R-SPEC-010  speculation phrased as fact        major     copy_issue
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from content_workflow.contracts import (
    ContentBriefV1,
    CopyDraftV1,
    MediaAssetV1,
    RetrievedFactV1,
)

from dmt_compliance.contracts import (
    ComplianceIssueV1,
    ReworkNode,
    Severity,
    SourceReferenceV1,
    claim_id_for,
)
from dmt_compliance.policy import ContentPolicyV1
from dmt_compliance.temporal import parse_utc

CHECKED_RULES: tuple[str, ...] = (
    "R-CITE-001",
    "R-EXP-002",
    "R-MKT-003",
    "R-CITE-011",
    "R-BAN-004",
    "R-CMP-005",
    "R-APR-006",
    "R-DIS-007",
    "R-LEN-008",
    "R-MED-009",
    "R-SPEC-010",
)


def _issue_id(rule_id: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join((rule_id, *parts)).encode("utf-8")).hexdigest()
    return f"iss-{digest[:16]}"


def _issue(
    rule_id: str,
    *,
    severity: Severity,
    detail: str,
    node: ReworkNode,
    claim_id: str | None = None,
    source: SourceReferenceV1 | None = None,
) -> ComplianceIssueV1:
    return ComplianceIssueV1(
        issue_id=_issue_id(rule_id, claim_id or "", detail),
        rule_id=rule_id,
        claim_id=claim_id,
        severity=severity,
        detail=detail,
        source_reference=source,
        suggested_rework_node=node,
    )


def _source_ref(claim: object) -> SourceReferenceV1 | None:
    citation = getattr(claim, "citation", None)
    if citation is None:
        return None
    return SourceReferenceV1(
        source_id=citation.source_id,
        source_version=citation.source_version,
        source_content_hash=citation.source_content_hash,
        market=citation.market,
        expires_at=citation.expires_at,
    )


def _citation_key(citation: object) -> tuple[str, str, str, str]:
    return (
        str(getattr(citation, "source_id")),
        str(getattr(citation, "source_version")),
        str(getattr(citation, "source_content_hash")),
        str(getattr(citation, "chunk_hash")),
    )


def _searchable_text(draft: CopyDraftV1, media: Sequence[MediaAssetV1]) -> str:
    parts = [draft.headline, draft.body]
    parts.extend(draft.disclosures)
    parts.extend(claim.text for claim in draft.claims)
    parts.extend(asset.alt_text for asset in media)
    return "\n".join(parts).lower()


def run_rules(
    *,
    policy: ContentPolicyV1,
    brief: ContentBriefV1,
    draft: CopyDraftV1,
    media: Sequence[MediaAssetV1],
    requested_media_types: Sequence[str],
    as_of: str,
    grounded_facts: Sequence[RetrievedFactV1] | None = None,
) -> tuple[ComplianceIssueV1, ...]:
    issues: list[ComplianceIssueV1] = []
    searchable = _searchable_text(draft, media)
    grounding_source = tuple(brief.facts if grounded_facts is None else grounded_facts)
    grounded_citations = {_citation_key(fact.citation) for fact in grounding_source}
    as_of_dt = parse_utc(as_of)

    # R-CITE-001 / R-EXP-002 / R-MKT-003: per-claim source rules.
    for claim in draft.claims:
        cid = claim_id_for(claim.text)
        if claim.citation is None:
            issues.append(
                _issue(
                    "R-CITE-001",
                    severity="critical",
                    detail=f"uncited claim: {claim.text[:160]}",
                    node="copy_issue",
                    claim_id=cid,
                )
            )
            continue
        source = _source_ref(claim)
        if (
            claim.citation.expires_at is not None
            and parse_utc(claim.citation.expires_at) <= as_of_dt
        ):
            issues.append(
                _issue(
                    "R-EXP-002",
                    severity="critical",
                    detail=(
                        f"claim source expired at {claim.citation.expires_at} "
                        f"(as_of {as_of}); refresh the fact bundle"
                    ),
                    node="fact_issue",
                    claim_id=cid,
                    source=source,
                )
            )
        if claim.citation.market != brief.market:
            issues.append(
                _issue(
                    "R-MKT-003",
                    severity="critical",
                    detail=(
                        f"claim cites {claim.citation.market} source but brief "
                        f"targets {brief.market}; cross-market facts forbidden"
                    ),
                    node="fact_issue",
                    claim_id=cid,
                    source=source,
                )
            )
        if grounded_citations and _citation_key(claim.citation) not in grounded_citations:
            issues.append(
                _issue(
                    "R-CITE-011",
                    severity="critical",
                    detail=(
                        "claim citation is not grounded in retrieved facts: "
                        f"{claim.citation.source_id}@{claim.citation.source_version}"
                    ),
                    node="fact_issue",
                    claim_id=cid,
                    source=source,
                )
            )

    # R-BAN-004: policy banned expressions (plus brief-level banned phrases).
    for banned in policy.banned_expressions:
        if banned.phrase.lower() in searchable:
            issues.append(
                _issue(
                    "R-BAN-004",
                    severity=banned.severity,
                    detail=f"banned expression: {banned.phrase}",
                    node="copy_issue",
                )
            )
    for phrase in brief.banned_phrases:
        if phrase.lower() in searchable and not any(
            i.rule_id == "R-BAN-004" and phrase.lower() in i.detail.lower()
            for i in issues
        ):
            issues.append(
                _issue(
                    "R-BAN-004",
                    severity="critical",
                    detail=f"banned expression: {phrase}",
                    node="copy_issue",
                )
            )

    # R-CMP-005: competitor comparison.
    named = [
        name for name in policy.competitor_names if name.lower() in searchable
    ]
    markers = [
        marker for marker in policy.comparison_markers if marker.lower() in searchable
    ]
    if named and markers:
        issues.append(
            _issue(
                "R-CMP-005",
                severity="major",
                detail=(
                    f"competitor comparison: mentions {', '.join(named)} with "
                    f"comparison marker {markers[0]!r}"
                ),
                node="copy_issue",
            )
        )

    # R-APR-006: fabricated regulator approval / certification claims.
    for pattern in policy.approval_claim_patterns:
        if pattern.lower() in searchable:
            issues.append(
                _issue(
                    "R-APR-006",
                    severity="critical",
                    detail=(
                        f"unsubstantiated regulator approval claim: {pattern!r}; "
                        "approval status may only come from approved sources"
                    ),
                    node="copy_issue",
                )
            )

    # R-DIS-007: required disclosures.
    for disclosure in brief.required_disclosures:
        if disclosure not in draft.disclosures and disclosure not in draft.body:
            issues.append(
                _issue(
                    "R-DIS-007",
                    severity="major",
                    detail=f"missing disclosure: {disclosure}",
                    node="copy_issue",
                )
            )

    # R-LEN-008: channel headline limit.
    if len(draft.headline) > brief.max_headline_chars:
        issues.append(
            _issue(
                "R-LEN-008",
                severity="minor",
                detail=(
                    f"headline {len(draft.headline)} chars exceeds channel limit "
                    f"{brief.max_headline_chars}"
                ),
                node="copy_issue",
            )
        )

    # R-MED-009: requested media types must exist.
    produced = {asset.media_type for asset in media}
    for media_type in requested_media_types:
        if media_type not in produced:
            issues.append(
                _issue(
                    "R-MED-009",
                    severity="major",
                    detail=f"missing media asset: {media_type}",
                    node="asset_issue",
                )
            )

    # R-SPEC-010: speculation phrased as fact.
    for marker in policy.speculation_markers:
        if marker.lower() in searchable:
            issues.append(
                _issue(
                    "R-SPEC-010",
                    severity="major",
                    detail=f"speculative phrasing presented as fact: {marker!r}",
                    node="copy_issue",
                )
            )

    return tuple(issues)
