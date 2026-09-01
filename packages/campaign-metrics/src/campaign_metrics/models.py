"""Data models for the campaign metrics pipeline (Phase 03 / Subphase 06).

Raw provider metrics are immutable and append-only; normalization is an
independent, recomputable layer. Missing values are never coerced to 0
and unreliable conversions surface as ``not_available`` — never imputed.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

QualityStatus = Literal["ok", "not_available"]

CANONICAL_METRICS: tuple[str, ...] = (
    "impressions",
    "clicks",
    "spend",
    "conversions",
    "ctr",
    "cpc",
    "cpm",
    "conversion_rate",
)


class MetricsError(Exception):
    """Base error for the campaign metrics pipeline."""


class RawImmutableError(MetricsError):
    """A raw metric row was re-registered with different content."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class RawMetricRecord(_Frozen):
    """One immutable raw provider metric value (master doc §11.1)."""

    metric_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    external_object_id: str = Field(min_length=1)
    provider_field_name: str = Field(min_length=1)
    provider_value: object | None
    provider_value_type: str = Field(min_length=1)
    provider_currency: str | None
    provider_timezone: str = Field(min_length=1)
    attribution_window: str = Field(min_length=1)
    period_start: str = Field(min_length=1)
    period_end: str = Field(min_length=1)
    provider_api_version: str = Field(min_length=1)
    retrieved_at: str = Field(min_length=1)
    source_response_ref: str = Field(min_length=1)
    source_response_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    connector_version: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)

    def dedupe_key(self) -> tuple[str, str, str, str, str, str]:
        return (
            self.channel,
            self.external_object_id,
            self.provider_field_name,
            self.period_start,
            self.period_end,
            self.source_response_hash,
        )


class NormalizedMetric(_Frozen):
    """One recomputable normalized metric value (master doc §11.2)."""

    metric_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    external_object_id: str = Field(min_length=1)
    canonical_metric: str = Field(min_length=1)
    value_decimal: Decimal | None
    quality_status: QualityStatus
    not_available_reason: str | None
    currency: str | None
    timezone: str | None
    period_start: str = Field(min_length=1)
    period_end: str = Field(min_length=1)
    formula_version: str = Field(min_length=1)
    source_raw_metric_ids: tuple[str, ...]
    freshness_retrieved_at: str | None
    calculated_at: str = Field(min_length=1)


class IngestContext(_Frozen):
    """Identity and provenance for one metrics ingest stream."""

    tenant_id: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    external_object_id: str = Field(min_length=1)
    period_start: str = Field(min_length=1)
    period_end: str = Field(min_length=1)
    provider_currency: str | None
    provider_timezone: str = Field(min_length=1)
    attribution_window: str = Field(min_length=1)
    provider_api_version: str = Field(min_length=1)
    connector_version: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    source_response_ref: str = Field(min_length=1)

    def stream_key(self) -> tuple[str, str, str, str, str, str]:
        return (
            self.tenant_id,
            self.channel,
            self.account_id,
            self.external_object_id,
            self.period_start,
            self.period_end,
        )


class IngestCheckpoint(_Frozen):
    """Cursor + watermark persisted after every page; survives restarts."""

    cursor: str | None
    watermark: str | None
    completed: bool
