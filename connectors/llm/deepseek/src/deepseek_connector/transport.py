"""Transports: the only layer that would touch the network.

In the repository and normal CI only deterministic mocks exist — no real
HTTP client is even implemented here. Real sandbox/live transport is
provided by the approved DEV pipeline (proxy + FQDN allowlist + secret
resolver); the connector refuses real modes without one.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Mapping, Protocol

from deepseek_connector.errors import ConnectorConfigError


class TransportTimeout(Exception):
    """Connect/request deadline exceeded (retryable)."""


@dataclass(frozen=True)
class TransportResponse:
    status_code: int
    headers: Mapping[str, str]
    body: str


class Transport(Protocol):
    """Send one wire payload; may raise :class:`TransportTimeout`."""

    def send(self, payload: Mapping[str, object], *, timeout_ms: int) -> TransportResponse:
        ...


@dataclass
class ScriptedTransport:
    """Deterministic scripted responses for retry/fault tests."""

    script: list[TransportResponse | TransportTimeout]
    sent_payloads: list[Mapping[str, object]] = field(default_factory=list)

    def send(self, payload: Mapping[str, object], *, timeout_ms: int) -> TransportResponse:
        self.sent_payloads.append(payload)
        if not self.script:
            raise AssertionError("scripted transport exhausted")
        step = self.script.pop(0)
        if isinstance(step, TransportTimeout):
            raise step
        return step


MockScenario = Literal[
    "normal",
    "uncited_claim",
    "refusal",
    "invalid_json",
    "rate_limited",
    "timeout",
    "server_error",
    "token_limit",
]

FACTS_MARKER = "FACTS_JSON:"
BRIEF_MARKER = "BRIEF_JSON:"


@dataclass
class FaultInjection:
    """Deterministic one-shot fault rates (seeded; no real randomness)."""

    enabled: bool = False
    timeout_rate: float = 0.0
    rate_limit_rate: float = 0.0
    server_error_rate: float = 0.0


class DeepSeekMockTransport:
    """Fixture-driven deterministic mock of the DeepSeek chat API.

    Never opens a socket. Grounded scenarios synthesize the structured
    draft strictly from the facts embedded in the request prompt, so the
    mock cannot invent product facts. Fault injection deterministically
    injects at most one transient failure per request before succeeding.
    """

    def __init__(
        self,
        fixture_dir: Path,
        *,
        scenario: MockScenario = "normal",
        seed: int = 20260907,
        faults: FaultInjection | None = None,
    ) -> None:
        if not fixture_dir.is_dir():
            raise ConnectorConfigError(f"mock fixture_dir not found: {fixture_dir}")
        self._fixture_dir = fixture_dir
        self._scenario: MockScenario = scenario
        self._rng = random.Random(seed)
        self._faults = faults or FaultInjection()
        self._fault_injected_for: set[str] = set()
        self.requests_served = 0

    def _fixture(self, name: str) -> dict[str, object]:
        path = self._fixture_dir / f"{name}.json"
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ConnectorConfigError(f"fixture {name} must be a JSON object")
        return {str(k): v for k, v in loaded.items()}

    def _response_from_fixture(self, name: str, content: str | None = None) -> TransportResponse:
        fixture = self._fixture(name)
        status_raw = fixture["status_code"]
        if not isinstance(status_raw, int):
            raise ConnectorConfigError(f"fixture {name} status_code must be an int")
        headers_raw = fixture.get("headers", {})
        headers: dict[str, str] = {}
        if isinstance(headers_raw, dict):
            headers = {str(k): str(v) for k, v in headers_raw.items()}
        body = fixture["body"]
        if isinstance(body, str):
            return TransportResponse(status_code=status_raw, headers=headers, body=body)
        text = json.dumps(body)
        if content is not None:
            text = text.replace("[[CONTENT_JSON]]", json.dumps(content)[1:-1])
        return TransportResponse(status_code=status_raw, headers=headers, body=text)

    def _maybe_inject_fault(self, key: str) -> TransportResponse | None:
        if not self._faults.enabled or key in self._fault_injected_for:
            return None
        roll = self._rng.random()
        if roll < self._faults.timeout_rate:
            self._fault_injected_for.add(key)
            raise TransportTimeout("mock injected timeout")
        if roll < self._faults.timeout_rate + self._faults.rate_limit_rate:
            self._fault_injected_for.add(key)
            return self._response_from_fixture("rate_limited")
        if roll < (
            self._faults.timeout_rate
            + self._faults.rate_limit_rate
            + self._faults.server_error_rate
        ):
            self._fault_injected_for.add(key)
            return self._response_from_fixture("server_error")
        return None

    def send(self, payload: Mapping[str, object], *, timeout_ms: int) -> TransportResponse:
        self.requests_served += 1
        key = json.dumps(payload, sort_keys=True)
        injected = self._maybe_inject_fault("sha:" + str(hash(key)))
        if injected is not None:
            return injected
        if self._scenario == "timeout":
            raise TransportTimeout("mock scenario timeout")
        if self._scenario in ("rate_limited", "server_error", "refusal", "invalid_json", "token_limit"):
            return self._response_from_fixture(self._scenario)
        content = self._grounded_content(payload, uncited=self._scenario == "uncited_claim")
        return self._response_from_fixture("normal", content=content)

    def _grounded_content(self, payload: Mapping[str, object], *, uncited: bool) -> str:
        facts, brief = _extract_prompt_data(payload)
        claims: list[dict[str, object]] = [
            {"text": fact["text"], "chunk_hash": fact["chunk_hash"]} for fact in facts
        ]
        if uncited:
            claims.append(
                {
                    "text": "Fabricated: 99% of patients prefer Product Alpha.",
                    "chunk_hash": None,
                }
            )
        max_chars_raw = brief.get("max_headline_chars", 80)
        max_chars = max_chars_raw if isinstance(max_chars_raw, int) else 80
        objective = str(brief.get("objective", "Draft"))
        headline = objective[: max_chars - 1].strip() or "Draft"
        disclosures_raw = brief.get("required_disclosures", [])
        disclosures = (
            [str(d) for d in disclosures_raw] if isinstance(disclosures_raw, list) else []
        )
        body_lines = [str(claim["text"]) for claim in claims] + disclosures
        draft = {
            "request_id": brief.get("request_id"),
            "channel": brief.get("channel"),
            "headline": headline,
            "body": "\n".join(body_lines),
            "claims": claims,
            "disclosures": disclosures,
        }
        return json.dumps(draft)


def _extract_prompt_data(
    payload: Mapping[str, object],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    messages = payload.get("messages")
    facts: list[dict[str, object]] = []
    brief: dict[str, object] = {}
    if isinstance(messages, list):
        for message in messages:
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if not isinstance(content, str):
                continue
            for line in content.splitlines():
                if line.startswith(FACTS_MARKER):
                    parsed = json.loads(line[len(FACTS_MARKER):])
                    if isinstance(parsed, list):
                        facts = [f for f in parsed if isinstance(f, dict)]
                elif line.startswith(BRIEF_MARKER):
                    parsed_brief = json.loads(line[len(BRIEF_MARKER):])
                    if isinstance(parsed_brief, dict):
                        brief = parsed_brief
    return facts, brief
