"""Fake model and media generators (repo/CI only; no real LLM/media API).

The fake model produces structured drafts deterministically from the brief;
it can be scripted to emit an uncited claim or schema-violating output so
tests can prove the workflow flags/blocks instead of faking success.
"""

from __future__ import annotations

import hashlib
from typing import Any, Literal, Protocol

from pydantic import ValidationError

from content_workflow.contracts import (
    ContentBriefV1,
    CopyClaimV1,
    CopyDraftV1,
    MediaAssetV1,
    MediaType,
)
from content_workflow.errors import InvalidNodeOutputError


class ContentModel(Protocol):
    """Boundary for the copy-generating model (fake in repo/CI)."""

    def generate_copy(self, brief: ContentBriefV1) -> CopyDraftV1:
        ...


class MediaGenerator(Protocol):
    """Boundary for the media generator (fake in repo/CI)."""

    @property
    def generator_id(self) -> str:
        ...

    def generate_media(
        self, brief: ContentBriefV1, media_type: MediaType
    ) -> MediaAssetV1:
        ...


FakeModelMode = Literal["grounded", "uncited_claim", "invalid_output"]


class FakeContentModel:
    """Deterministic structured drafts; every claim cites a retrieved fact."""

    model_id = "fake-content-model-v1"

    def __init__(self, *, mode: FakeModelMode = "grounded") -> None:
        self._mode = mode

    def generate_copy(self, brief: ContentBriefV1) -> CopyDraftV1:
        if self._mode == "invalid_output":
            # 模拟模型返回非法结构：类型化失败，不得用默认值伪造成功。
            raw: dict[str, Any] = {"schema_version": "1.0", "headline": ""}
            try:
                return CopyDraftV1.model_validate(raw)
            except ValidationError as exc:
                raise InvalidNodeOutputError(
                    f"fake model output violates CopyDraftV1: {exc}"
                ) from exc
        claims = [
            CopyClaimV1(text=fact.text, citation=fact.citation)
            for fact in brief.facts
        ]
        if self._mode == "uncited_claim":
            claims.append(
                CopyClaimV1(
                    text="Fabricated: 99% of patients prefer Product Alpha.",
                    citation=None,
                )
            )
        headline = f"{brief.objective[: brief.max_headline_chars - 1].strip()}"
        body_lines = [claim.text for claim in claims]
        body_lines.extend(brief.required_disclosures)
        return CopyDraftV1(
            request_id=brief.request_id,
            channel=brief.channel,
            headline=headline or "Draft",
            body="\n".join(body_lines),
            claims=tuple(claims),
            disclosures=brief.required_disclosures,
            model_id=self.model_id,
        )


class FakeMediaGenerator:
    """Deterministic media references (no binary, no real generation API)."""

    generator_id = "fake-media-v1"

    def generate_media(
        self, brief: ContentBriefV1, media_type: MediaType
    ) -> MediaAssetV1:
        seed = f"{brief.request_id}:{brief.channel}:{media_type}:{brief.tone}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        return MediaAssetV1(
            request_id=brief.request_id,
            asset_id=f"asset-{digest[:12]}",
            media_type=media_type,
            uri=f"fake://media/{digest}",
            sha256=f"sha256:{digest}",
            alt_text=f"{media_type} draft for {brief.objective[:80]}",
            generator_id=self.generator_id,
        )
