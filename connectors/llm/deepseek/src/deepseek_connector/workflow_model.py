"""Bridge from the DeepSeek connector to the Content Workflow model slot.

``DeepSeekContentModel`` implements the ``ContentModel`` protocol used by
the ``BuildBrief``/``GenerateCopy`` nodes, so the workflow can switch
between the fake model and the (mock or approved-DEV) DeepSeek connector
without touching the graph.

Model-returned citations are untrusted: the model may only *reference* a
retrieved fact by its ``chunk_hash``; the actual :class:`Citation` object
is always resolved from the brief's RAG facts. Unknown or missing
references become uncited claims, which compliance flags and blocks.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from content_workflow.contracts import ContentBriefV1, CopyClaimV1, CopyDraftV1
from content_workflow.errors import InvalidNodeOutputError
from deepseek_connector.connector import DeepSeekConnector
from deepseek_connector.contracts import ChatMessageV1, ChatRequestV1
from deepseek_connector.errors import DeepSeekConnectorError
from deepseek_connector.transport import BRIEF_MARKER, FACTS_MARKER
from product_rag.citations import Citation

PROMPT_VERSION = "content-copy-prompt/1.0.0"

_SYSTEM_PROMPT = (
    "You generate marketing copy drafts. Use ONLY the approved facts "
    "provided; every claim must reference a fact by its chunk_hash. "
    "Respond with a single JSON object: request_id, channel, headline, "
    "body, claims (list of {text, chunk_hash}), disclosures."
)


class DeepSeekContentModel:
    """ContentModel implementation backed by the DeepSeek connector."""

    def __init__(self, connector: DeepSeekConnector) -> None:
        self._connector = connector
        self.model_id = f"deepseek:{connector.runtime.chat_model}"

    def generate_copy(self, brief: ContentBriefV1) -> CopyDraftV1:
        request = self._build_request(brief)
        try:
            result = self._connector.execute(
                request, trace_id=f"content-{brief.request_id}"
            )
        except DeepSeekConnectorError as exc:
            # 类型化透传：不静默退回 Fake,由工作流/上层决定重试或阻断。
            raise InvalidNodeOutputError(
                f"deepseek connector failed ({exc.code}): {exc}"
            ) from exc
        return self._parse_draft(brief, result.content)

    def _build_request(self, brief: ContentBriefV1) -> ChatRequestV1:
        facts_payload = [
            {"chunk_hash": fact.citation.chunk_hash, "text": fact.text}
            for fact in brief.facts
        ]
        brief_payload = {
            "request_id": brief.request_id,
            "channel": brief.channel,
            "objective": brief.objective,
            "tone": brief.tone,
            "max_headline_chars": brief.max_headline_chars,
            "required_disclosures": list(brief.required_disclosures),
            "banned_phrases": list(brief.banned_phrases),
            "target_audience": list(brief.target_audience),
        }
        user_content = "\n".join(
            [
                "Generate the copy draft for the brief below.",
                f"{BRIEF_MARKER}{json.dumps(brief_payload)}",
                f"{FACTS_MARKER}{json.dumps(facts_payload)}",
            ]
        )
        runtime = self._connector.runtime
        return ChatRequestV1(
            request_id=brief.request_id,
            prompt_version=PROMPT_VERSION,
            messages=(
                ChatMessageV1(role="system", content=_SYSTEM_PROMPT),
                ChatMessageV1(role="user", content=user_content),
            ),
            temperature=runtime.temperature,
            max_output_tokens=runtime.max_output_tokens,
        )

    def _parse_draft(self, brief: ContentBriefV1, content: str) -> CopyDraftV1:
        try:
            raw: Any = json.loads(content)
        except json.JSONDecodeError as exc:
            raise InvalidNodeOutputError(
                "model output is not valid JSON; refusing to fabricate a draft"
            ) from exc
        if not isinstance(raw, dict):
            raise InvalidNodeOutputError("model output must be a JSON object")
        citations_by_hash: dict[str, Citation] = {
            fact.citation.chunk_hash: fact.citation for fact in brief.facts
        }
        claims_raw = raw.get("claims")
        if not isinstance(claims_raw, list):
            raise InvalidNodeOutputError("model output missing claims list")
        claims: list[CopyClaimV1] = []
        for entry in claims_raw:
            if not isinstance(entry, dict) or not isinstance(entry.get("text"), str):
                raise InvalidNodeOutputError("model claim entry malformed")
            chunk_hash = entry.get("chunk_hash")
            citation = (
                citations_by_hash.get(chunk_hash)
                if isinstance(chunk_hash, str)
                else None
            )
            claims.append(CopyClaimV1(text=entry["text"], citation=citation))
        try:
            return CopyDraftV1(
                request_id=brief.request_id,
                channel=brief.channel,
                headline=raw.get("headline", ""),
                body=raw.get("body", ""),
                claims=tuple(claims),
                disclosures=brief.required_disclosures,
                model_id=self.model_id,
            )
        except ValidationError as exc:
            raise InvalidNodeOutputError(
                f"model output violates CopyDraftV1: {exc}"
            ) from exc
