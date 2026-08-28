"""Shared builders for compliance tests: briefs, drafts, media, citations."""

from __future__ import annotations

import hashlib

from content_workflow.contracts import (
    ContentBriefV1,
    CopyClaimV1,
    CopyDraftV1,
    MediaAssetV1,
)
from product_rag.citations import Citation

AS_OF = "2026-06-01T00:00:00Z"
DISCLOSURE = "See full prescribing information."


def make_citation(
    *,
    market: str = "US",
    expires_at: str | None = "2027-01-01T00:00:00Z",
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
        source_content_hash="sha256:" + hashlib.sha256(source_id.encode()).hexdigest(),
        chunk_hash="sha256:" + hashlib.sha256(f"chunk-{source_id}".encode()).hexdigest(),
    )


def make_brief(**overrides: object) -> ContentBriefV1:
    base: dict[str, object] = {
        "request_id": "req-0001",
        "tenant": "tenant-cshi",
        "market": "US",
        "locale": "en-US",
        "channel": "linkedin",
        "objective": "Introduce Product Alpha dosing to physicians",
        "target_audience": ("physicians",),
        "tone": "professional",
        "facts": (),
        "banned_phrases": ("cure-all",),
        "required_disclosures": (DISCLOSURE,),
        "max_headline_chars": 150,
        "skill_versions": (("skill-brand-core", "1.2.0"),),
    }
    base.update(overrides)
    return ContentBriefV1.model_validate(base)


def make_claim(
    text: str = "Product Alpha is dosed once daily.",
    *,
    citation: Citation | None = None,
    cited: bool = True,
    market: str = "US",
    expires_at: str | None = "2027-01-01T00:00:00Z",
) -> CopyClaimV1:
    if citation is None and cited:
        citation = make_citation(market=market, expires_at=expires_at)
    return CopyClaimV1(text=text, citation=citation)


def make_draft(
    *,
    headline: str = "Product Alpha dosing overview",
    body: str | None = None,
    claims: tuple[CopyClaimV1, ...] | None = None,
    disclosures: tuple[str, ...] = (DISCLOSURE,),
) -> CopyDraftV1:
    if claims is None:
        claims = (make_claim(),)
    if body is None:
        body = "\n".join([claim.text for claim in claims] + list(disclosures))
    return CopyDraftV1(
        request_id="req-0001",
        channel="linkedin",
        headline=headline,
        body=body,
        claims=claims,
        disclosures=disclosures,
        model_id="fake-content-model-v1",
    )


def make_media() -> MediaAssetV1:
    digest = hashlib.sha256(b"asset").hexdigest()
    return MediaAssetV1(
        request_id="req-0001",
        asset_id="asset-000000000001",
        media_type="image",
        uri=f"fake://media/{digest}",
        sha256=f"sha256:{digest}",
        alt_text="image draft",
        generator_id="fake-media-v1",
    )
