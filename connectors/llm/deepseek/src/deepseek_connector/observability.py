"""Observability: hash-and-version records only — never bodies or secrets.

Each attempt/outcome is journaled with the request hash, model, prompt and
config versions, token usage and estimated cost. ``log_request_body`` and
``log_response_body`` are hard-false in config; this module has no field
that could even carry a body.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Outcome = Literal[
    "success",
    "retryable_failure",
    "fatal_failure",
    "budget_refused",
    "queue_refused",
]


@dataclass(frozen=True)
class RequestRecord:
    """One journal line for a connector attempt or outcome."""

    trace_id: str
    request_hash: str
    mode: str
    model: str
    prompt_version: str
    config_hash: str
    attempt: int
    outcome: Outcome
    status_code: int | None
    error_code: str | None
    prompt_tokens: int
    completion_tokens: int
    estimated_cost: float
    retry_delay_ms: int | None = None


@dataclass
class ConnectorJournal:
    """In-memory journal; the API/worker layer persists it to audit."""

    records: list[RequestRecord] = field(default_factory=list)

    def append(self, record: RequestRecord) -> None:
        self.records.append(record)

    def total_cost(self) -> float:
        return round(sum(r.estimated_cost for r in self.records if r.outcome == "success"), 8)
