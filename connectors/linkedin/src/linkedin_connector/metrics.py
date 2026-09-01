"""Ads Reporting metrics reads: raw fields preserved, cursor pagination.

Rows keep the provider field name, raw value and type verbatim (missing
stays missing — never coerced to ``0``), plus retrieval metadata and a
source-response hash so raw metrics can be stored immutably. The mock
path reads deterministic fixture pages; real reads happen only in
protected DEV/SIT jobs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from linkedin_connector.config import LinkedInConnectorConfig

_REPO_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class MetricRow:
    """One raw provider metric value with retrieval metadata."""

    provider_field_name: str
    provider_value: object
    provider_value_type: str
    provider_fields: Mapping[str, object]
    period_start: str
    period_end: str
    retrieved_at: str
    source_response_hash: str


@dataclass(frozen=True)
class MetricsPage:
    """One page of raw metric rows plus the next cursor (None = done)."""

    rows: tuple[MetricRow, ...]
    next_cursor: str | None


def _response_hash(document: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_fixture_pages(config: LinkedInConnectorConfig) -> list[dict[str, Any]]:
    fixture_path = _REPO_ROOT / config.mock.fixture_set
    document = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
    pages: list[dict[str, Any]] = document["metrics"]["pages"]
    return pages


def fetch_metrics_page(
    *,
    config: LinkedInConnectorConfig,
    account_id: str,
    external_object_id: str,
    window: Mapping[str, str],
    cursor: str | None,
    retrieved_at: str,
) -> MetricsPage:
    """Fetch one deterministic page of raw metrics from the mock fixtures."""
    pages = _load_fixture_pages(config)
    page = next((p for p in pages if p["cursor"] == cursor), None)
    if page is None:
        raise ValueError(f"unknown metrics cursor {cursor!r}")
    response_document = {
        "account_id": account_id,
        "external_object_id": external_object_id,
        "window": dict(window),
        "cursor": cursor,
        "rows": page["rows"],
    }
    source_hash = _response_hash(response_document)
    rows = tuple(
        MetricRow(
            provider_field_name=str(row["field"]),
            provider_value=row["value"],
            provider_value_type=str(row["value_type"]),
            provider_fields=dict(row),
            period_start=window["start"],
            period_end=window["end"],
            retrieved_at=retrieved_at,
            source_response_hash=source_hash,
        )
        for row in page["rows"]
    )
    return MetricsPage(rows=rows, next_cursor=page["next_cursor"])
