"""GAQL metrics reads via GoogleAdsService: raw fields preserved,
page-token pagination, per-page response hashes.

Rows keep the provider field name, raw value and type verbatim (cost
stays in micros as an int64 string; missing stays missing — never coerced
to ``0``), plus retrieval metadata, the GAQL query text and a
source-response hash so raw metrics can be stored immutably. The mock
path reads deterministic fixture pages; real GoogleAdsService.Search /
SearchStream calls happen only in protected DEV/SIT jobs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from google_ads_connector.config import GoogleAdsConnectorConfig

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
    gaql_query: str
    source_response_hash: str


@dataclass(frozen=True)
class GaqlPage:
    """One page of raw metric rows plus the next page token (None = done)."""

    rows: tuple[MetricRow, ...]
    next_page_token: str | None


def _response_hash(document: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_fixture(config: GoogleAdsConnectorConfig) -> dict[str, Any]:
    fixture_path = _REPO_ROOT / config.mock.fixture_set
    document: dict[str, Any] = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
    return document


def fetch_gaql_page(
    *,
    config: GoogleAdsConnectorConfig,
    customer_id_ref: str,
    external_object_id: str,
    window: Mapping[str, str],
    page_token: str | None,
    retrieved_at: str,
) -> GaqlPage:
    """Fetch one deterministic GAQL result page from the mock fixtures."""
    fixture = _load_fixture(config)
    gaql_query = str(fixture["gaql"]["query_template"]).format(
        start=window["start"], end=window["end"]
    )
    pages: list[dict[str, Any]] = fixture["metrics"]["pages"]
    page = next((p for p in pages if p["page_token"] == page_token), None)
    if page is None:
        raise ValueError(f"unknown page_token {page_token!r}")
    response_document = {
        "customer_id_ref": customer_id_ref,
        "external_object_id": external_object_id,
        "window": dict(window),
        "page_token": page_token,
        "gaql_query": gaql_query,
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
            gaql_query=gaql_query,
            source_response_hash=source_hash,
        )
        for row in page["rows"]
    )
    return GaqlPage(rows=rows, next_page_token=page["next_page_token"])
