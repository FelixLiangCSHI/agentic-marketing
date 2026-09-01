"""Shared test builders for campaign-metrics."""

from __future__ import annotations

from typing import Any

from campaign_metrics.models import IngestContext, RawMetricRecord
from campaign_metrics.stores import (
    FakeNormalizedMetricStore,
    FakeRawMetricStore,
    FakeWatermarkStore,
)

FAKE_NOW = "2026-09-14T00:00:00Z"
WINDOW = {"start": "2026-09-07", "end": "2026-09-13"}


def make_context(**overrides: Any) -> IngestContext:
    values: dict[str, Any] = {
        "tenant_id": "tenant-a",
        "channel": "linkedin",
        "account_id": "acct-1",
        "external_object_id": "urn:li:sponsoredCampaign:1001",
        "period_start": WINDOW["start"],
        "period_end": WINDOW["end"],
        "provider_currency": "USD",
        "provider_timezone": "UTC",
        "attribution_window": "LAST_TOUCH_7D",
        "provider_api_version": "202409",
        "connector_version": "linkedin-connector-0.1.0",
        "trace_id": "trace-p3-0006",
        "source_response_ref": "objectstore://local/tenant-a/metrics/raw-page-1.json",
    }
    values.update(overrides)
    return IngestContext(**values)


def make_raw(**overrides: Any) -> RawMetricRecord:
    values: dict[str, Any] = {
        "metric_id": "raw-0001",
        "tenant_id": "tenant-a",
        "channel": "linkedin",
        "account_id": "acct-1",
        "external_object_id": "urn:li:sponsoredCampaign:1001",
        "provider_field_name": "impressions",
        "provider_value": 12450,
        "provider_value_type": "integer",
        "provider_currency": "USD",
        "provider_timezone": "UTC",
        "attribution_window": "LAST_TOUCH_7D",
        "period_start": WINDOW["start"],
        "period_end": WINDOW["end"],
        "provider_api_version": "202409",
        "retrieved_at": FAKE_NOW,
        "source_response_ref": "objectstore://local/tenant-a/metrics/raw-page-1.json",
        "source_response_hash": "sha256:" + "a" * 64,
        "connector_version": "linkedin-connector-0.1.0",
        "trace_id": "trace-p3-0006",
    }
    values.update(overrides)
    return RawMetricRecord(**values)


def make_raw_set(
    *,
    channel: str = "linkedin",
    impressions: object = 12450,
    impressions_type: str = "integer",
    clicks: object = 311,
    clicks_type: str = "integer",
    spend: object = "413.27",
    spend_type: str = "decimal_string",
    conversions: object = None,
    conversions_type: str = "missing",
    currency: str | None = "USD",
    spend_field: str | None = None,
) -> tuple[RawMetricRecord, ...]:
    if channel == "google_ads":
        field_names = {
            "impressions": "metrics.impressions",
            "clicks": "metrics.clicks",
            "spend": spend_field or "metrics.cost_micros",
            "conversions": "metrics.conversions",
        }
    else:
        field_names = {
            "impressions": "impressions",
            "clicks": "clicks",
            "spend": spend_field or "costInLocalCurrency",
            "conversions": "conversions",
        }
    specs: list[tuple[str, object, str, str | None]] = [
        (field_names["impressions"], impressions, impressions_type, None),
        (field_names["clicks"], clicks, clicks_type, None),
        (field_names["spend"], spend, spend_type, currency),
        (field_names["conversions"], conversions, conversions_type, None),
    ]
    records = []
    for index, (field, value, value_type, row_currency) in enumerate(specs):
        records.append(
            make_raw(
                metric_id=f"raw-{channel}-{index:04d}",
                channel=channel,
                provider_field_name=field,
                provider_value=value,
                provider_value_type=value_type,
                provider_currency=row_currency,
            )
        )
    return tuple(records)


class Harness:
    def __init__(self) -> None:
        self.raw_store = FakeRawMetricStore()
        self.normalized_store = FakeNormalizedMetricStore()
        self.watermark_store = FakeWatermarkStore()
