"""Versioned request/result contracts for the DeepSeek connector.

The chat request/result are the connector's internal contract; the wire
payload is derived from the request. ``request_hash`` binds retries to an
identical request (``retry_requires_same_request_hash``).
"""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

Role = Literal["system", "user"]
FinishReason = Literal["stop", "length", "content_filter"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"


class ChatMessageV1(_Model):
    role: Role
    content: Annotated[StrictStr, Field(min_length=1, max_length=64000)]


class ChatRequestV1(_Model):
    """One chat completion request (structured JSON output demanded)."""

    request_id: Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")]
    prompt_version: Annotated[StrictStr, Field(min_length=1, max_length=64)]
    messages: Annotated[tuple[ChatMessageV1, ...], Field(min_length=1, max_length=32)]
    temperature: Annotated[float, Field(ge=0.0, le=2.0)]
    max_output_tokens: Annotated[StrictInt, Field(ge=1)]
    response_format: Literal["json_object"] = "json_object"

    def wire_payload(self, model: str) -> dict[str, object]:
        """OpenAI-compatible body actually sent to the provider."""
        return {
            "model": model,
            "messages": [
                {"role": m.role, "content": m.content} for m in self.messages
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_output_tokens,
            "response_format": {"type": "json_object"},
            "stream": False,
        }


class ChatUsageV1(_Model):
    prompt_tokens: Annotated[StrictInt, Field(ge=0)]
    completion_tokens: Annotated[StrictInt, Field(ge=0)]
    total_tokens: Annotated[StrictInt, Field(ge=0)]
    estimated_cost: Annotated[float, Field(ge=0.0)]


class ChatResultV1(_Model):
    """Validated result of one chat completion."""

    request_id: StrictStr
    model: StrictStr
    content: Annotated[StrictStr, Field(min_length=1)]
    finish_reason: FinishReason
    usage: ChatUsageV1
    provider_request_id: StrictStr | None


def request_hash(request: ChatRequestV1, *, model: str, config_hash: str) -> str:
    """Deterministic hash binding a request to model + config version."""
    payload = json.dumps(
        {
            "request": request.model_dump(mode="json"),
            "model": model,
            "config_hash": config_hash,
        },
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
