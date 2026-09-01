"""Shared builders for package tests."""

from __future__ import annotations

import hashlib
from typing import Any

from content_workflow.contracts import (
    ContentBriefV1,
    CopyClaimV1,
    CopyDraftV1,
    MediaAssetV1,
    model_hash,
)
from product_rag.citations import Citation

from content_package import (
    PackageApprovalV1,
    PackageInputs,
    VersionBindingsV1,
    canonical_content_hash,
)
from dmt_compliance import ComplianceEngine, DEFAULT_POLICY_PATH, load_policy

AS_OF = "2026-06-01T00:00:00Z"
EXPIRES_AT = "2027-01-01T00:00:00Z"
DISCLOSURE = "See full prescribing information."

ENGINE = ComplianceEngine(load_policy(DEFAULT_POLICY_PATH))


def make_citation(
    *,
    market: str = "US",
    expires_at: str | None = EXPIRES_AT,
    source_id: str = "doc-alpha-pi",
) -> Citation:
    return Citation(
        source_id=source_id,
        source_version="1.0.0",
        product_id="product-alpha",
        tenant="tenant-cshi",
        market=market,  # type: ignore[arg-type]
        locale="en-US",
        char_start=0,
        char_end=42,
        effective_from="2026-01-01T00:00:00Z",
        expires_at=expires_at,
        source_content_hash="sha256:"
        + hashlib.sha256(source_id.encode()).hexdigest(),
        chunk_hash="sha256:"
        + hashlib.sha256(f"chunk-{source_id}".encode()).hexdigest(),
    )


def make_claim(
    text: str = "Product Alpha is taken once daily.",
    *,
    cited: bool = True,
    expires_at: str | None = EXPIRES_AT,
) -> CopyClaimV1:
    return CopyClaimV1(
        text=text,
        citation=make_citation(expires_at=expires_at) if cited else None,
    )


def make_brief(**overrides: Any) -> ContentBriefV1:
    payload: dict[str, Any] = {
        "request_id": "req-0001",
        "tenant": "tenant-cshi",
        "market": "US",
        "locale": "en-US",
        "channel": "linkedin",
        "objective": "Introduce Product Alpha dosing",
        "target_audience": ("physicians",),
        "tone": "professional",
        "facts": (),
        "banned_phrases": ("cure-all",),
        "required_disclosures": (DISCLOSURE,),
        "max_headline_chars": 150,
        "skill_versions": (),
    }
    payload.update(overrides)
    return ContentBriefV1.model_validate(payload)


def make_draft(
    *,
    headline: str = "Product Alpha dosing overview",
    claims: tuple[CopyClaimV1, ...] | None = None,
    disclosures: tuple[str, ...] = (DISCLOSURE,),
) -> CopyDraftV1:
    if claims is None:
        claims = (make_claim(),)
    body = " ".join([claim.text for claim in claims] + list(disclosures))
    return CopyDraftV1(
        request_id="req-0001",
        channel="linkedin",
        headline=headline,
        body=body,
        claims=claims,
        disclosures=disclosures,
        model_id="fake-content-model-v1",
    )


def make_media(seed: str = "hero") -> MediaAssetV1:
    return MediaAssetV1(
        request_id="req-0001",
        asset_id=f"asset-{seed}",
        media_type="image",
        uri=f"object://local/tenant-cshi/content-agent-approved/run-0001/{seed}.png",
        sha256="sha256:" + hashlib.sha256(seed.encode()).hexdigest(),
        alt_text=f"Product Alpha {seed} image",
        generator_id="fake-media-generator-v1",
    )


def make_versions(**overrides: Any) -> VersionBindingsV1:
    payload: dict[str, Any] = {
        "policy_version": "1.0.0",
        "prompt_version": "1.0.0",
        "model_id": "fake-content-model-v1",
        "workflow_version": "0.1.0",
        "skill_versions": (("copywriting", "1.0.0"),),
    }
    payload.update(overrides)
    return VersionBindingsV1.model_validate(payload)


def expected_content_hash(
    draft: CopyDraftV1,
    media: tuple[MediaAssetV1, ...],
    versions: VersionBindingsV1,
    channel_variants: tuple[tuple[str, tuple[str, ...]], ...],
    tenant_id: str = "tenant-cshi",
    asset_hashes: tuple[str, ...] | None = None,
) -> str:
    from content_package import ClaimBindingV1

    claims = tuple(
        ClaimBindingV1(
            text=claim.text,
            source_id=claim.citation.source_id,
            source_version=claim.citation.source_version,
            source_excerpt_hash=claim.citation.chunk_hash,
            expires_at=claim.citation.expires_at,
        )
        for claim in draft.claims
        if claim.citation is not None
    )
    return canonical_content_hash(
        copy_hash=model_hash(draft),
        tenant_id=tenant_id,
        claims=claims,
        asset_hashes=asset_hashes or tuple(asset.sha256 for asset in media),
        versions=versions,
        channel_variants=channel_variants,
    )


def make_approval(
    track: str,
    *,
    artifact_hash: str,
    approved_by: str | None = None,
    approved_at: str = "2026-05-30T12:00:00Z",
) -> PackageApprovalV1:
    return PackageApprovalV1(
        track=track,  # type: ignore[arg-type]
        approval_id=f"rev-{track}-0001",
        approved_by=approved_by or f"emp-{track}",
        approved_at=approved_at,
        artifact_hash=artifact_hash,
    )


def make_inputs(**overrides: Any) -> PackageInputs:
    draft = overrides.pop("draft", make_draft())
    media = overrides.pop("media", (make_media(),))
    versions = overrides.pop("versions", make_versions())
    channel_variants = overrides.pop(
        "channel_variants", (("linkedin", ("cv-req-0001",)),)
    )
    tenant_id = overrides.get("tenant_id", "tenant-cshi")
    asset_hashes = overrides.get(
        "asset_hashes", tuple(asset.sha256 for asset in media)
    )
    content_hash = expected_content_hash(
        draft,
        media,
        versions,
        channel_variants,
        tenant_id=tenant_id,
        asset_hashes=asset_hashes,
    )
    compliance_result = overrides.pop(
        "compliance_result",
        ENGINE.evaluate(
            brief=make_brief(),
            draft=draft,
            media=media,
            requested_media_types=("image",),
            as_of=AS_OF,
        ),
    )
    approvals = overrides.pop(
        "approvals",
        (
            make_approval("medical", artifact_hash=content_hash),
            make_approval("marketing", artifact_hash=content_hash),
        ),
    )
    payload: dict[str, Any] = {
        "product_id": "product-alpha",
        "tenant_id": tenant_id,
        "market": "US",
        "locale": "en-US",
        "target_audience": ("physicians",),
        "draft": draft,
        "media": media,
        "asset_uris": tuple(asset.uri for asset in media),
        "asset_hashes": asset_hashes,
        "requested_channels": ("linkedin",),
        "channel_variants": channel_variants,
        "compliance_result": compliance_result,
        "approvals": approvals,
        "versions": versions,
        "expires_at": EXPIRES_AT,
    }
    payload.update(overrides)
    return PackageInputs(**payload)
