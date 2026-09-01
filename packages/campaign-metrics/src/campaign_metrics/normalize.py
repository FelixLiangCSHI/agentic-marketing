"""Deterministic normalization: Decimal math, versioned formulas.

Precise numbers are computed by this deterministic code only; model
output must never overwrite them (master doc §11.2). Anything that
cannot be converted reliably becomes ``not_available`` — never 0 and
never an imputed value.

Formula ``fv1``:
    ctr             = clicks / impressions          (matches src/analysis:
                      "SUM(clicks) ÷ SUM(impressions)")
    cpc             = spend / clicks
    cpm             = spend / impressions * 1000
    conversion_rate = conversions / clicks
"""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from campaign_metrics.models import MetricsError, NormalizedMetric, RawMetricRecord

FORMULA_VERSION = "fv1"


class NormalizationInputError(MetricsError):
    """The raw inputs mix tenants, accounts, objects or time windows."""

_MICROS = Decimal("1000000")

# provider field -> (canonical metric, is_money, micros_scaled)
_FIELD_MAPS: Mapping[str, Mapping[str, tuple[str, bool, bool]]] = {
    "linkedin": {
        "impressions": ("impressions", False, False),
        "clicks": ("clicks", False, False),
        "costInLocalCurrency": ("spend", True, False),
        "conversions": ("conversions", False, False),
    },
    "google_ads": {
        "metrics.impressions": ("impressions", False, False),
        "metrics.clicks": ("clicks", False, False),
        "metrics.cost_micros": ("spend", True, True),
        "metrics.conversions": ("conversions", False, False),
    },
}

_BASE_METRICS = ("impressions", "clicks", "spend", "conversions")


def _convert(record: RawMetricRecord, micros_scaled: bool) -> Decimal | None:
    if record.provider_value is None or record.provider_value_type == "missing":
        return None
    value = record.provider_value
    if record.provider_value_type == "integer" and isinstance(value, int):
        result = Decimal(value)
    elif record.provider_value_type in ("decimal_string", "int64_string") and isinstance(
        value, str
    ):
        result = Decimal(value)
    else:
        return None
    if micros_scaled:
        result = result / _MICROS
    return result


def _metric(
    *,
    template: RawMetricRecord,
    canonical_metric: str,
    value: Decimal | None,
    reason: str | None,
    currency: str | None,
    source_ids: tuple[str, ...],
    freshness: str | None,
    calculated_at: str,
) -> NormalizedMetric:
    return NormalizedMetric(
        metric_id=(
            f"nm-{template.tenant_id}-{template.account_id}"
            f"-{template.channel}-{template.external_object_id}"
            f"-{canonical_metric}-{template.period_start}-{FORMULA_VERSION}"
        ),
        tenant_id=template.tenant_id,
        channel=template.channel,
        external_object_id=template.external_object_id,
        canonical_metric=canonical_metric,
        value_decimal=value,
        quality_status="ok" if value is not None else "not_available",
        not_available_reason=reason,
        currency=currency,
        timezone=template.provider_timezone,
        period_start=template.period_start,
        period_end=template.period_end,
        formula_version=FORMULA_VERSION,
        source_raw_metric_ids=source_ids,
        freshness_retrieved_at=freshness,
        calculated_at=calculated_at,
    )


def normalize(
    raw_records: tuple[RawMetricRecord, ...], *, calculated_at: str
) -> tuple[NormalizedMetric, ...]:
    """Compute the canonical metric set from immutable raw records."""
    if not raw_records:
        return ()
    template = raw_records[0]
    for record in raw_records:
        if (
            record.tenant_id != template.tenant_id
            or record.channel != template.channel
            or record.account_id != template.account_id
            or record.external_object_id != template.external_object_id
            or record.period_start != template.period_start
            or record.period_end != template.period_end
        ):
            raise NormalizationInputError(
                f"raw metric {record.metric_id!r} belongs to a different "
                "tenant/account/object/time window than the batch"
            )
    field_map = _FIELD_MAPS.get(template.channel, {})

    grouped: dict[str, list[tuple[RawMetricRecord, bool, bool]]] = {}
    for record in raw_records:
        mapped = field_map.get(record.provider_field_name)
        if mapped is None:
            continue
        canonical, is_money, micros_scaled = mapped
        grouped.setdefault(canonical, []).append((record, is_money, micros_scaled))

    base: dict[str, NormalizedMetric] = {}
    for canonical in _BASE_METRICS:
        rows = grouped.get(canonical)
        if not rows:
            continue
        records = [row[0] for row in rows]
        is_money = rows[0][1]
        micros_scaled = rows[0][2]
        source_ids = tuple(r.metric_id for r in records)
        freshness = max(r.retrieved_at for r in records)

        reason: str | None = None
        if len({r.provider_timezone for r in records}) > 1:
            reason = "timezone_mismatch"
        elif len({r.attribution_window for r in records}) > 1:
            reason = "attribution_window_mismatch"
        elif is_money and len({r.provider_currency for r in records}) > 1:
            reason = "currency_mismatch"
        elif is_money and records[0].provider_currency is None:
            reason = "currency_unknown"

        currency = records[0].provider_currency if is_money and reason is None else None
        if reason is not None:
            base[canonical] = _metric(
                template=template,
                canonical_metric=canonical,
                value=None,
                reason=reason,
                currency=None,
                source_ids=source_ids,
                freshness=freshness,
                calculated_at=calculated_at,
            )
            continue

        latest = max(records, key=lambda r: r.retrieved_at)
        value = _convert(latest, micros_scaled)
        base[canonical] = _metric(
            template=template,
            canonical_metric=canonical,
            value=value,
            reason=(
                None
                if value is not None
                else (
                    "provider_reported_missing"
                    if latest.provider_value is None
                    or latest.provider_value_type == "missing"
                    else "unsupported_value_type"
                )
            ),
            currency=currency,
            source_ids=(latest.metric_id,),
            freshness=latest.retrieved_at,
            calculated_at=calculated_at,
        )

    derived_specs: tuple[tuple[str, str, str, Decimal, bool], ...] = (
        # (canonical, numerator, denominator, scale, money)
        ("ctr", "clicks", "impressions", Decimal(1), False),
        ("cpc", "spend", "clicks", Decimal(1), True),
        ("cpm", "spend", "impressions", Decimal(1000), True),
        ("conversion_rate", "conversions", "clicks", Decimal(1), False),
    )

    derived: list[NormalizedMetric] = []
    for canonical, num_name, den_name, scale, is_money in derived_specs:
        numerator = base.get(num_name)
        denominator = base.get(den_name)
        if numerator is None or denominator is None:
            continue
        source_ids = tuple(
            dict.fromkeys(
                numerator.source_raw_metric_ids + denominator.source_raw_metric_ids
            )
        )
        freshness_values = [
            f
            for f in (numerator.freshness_retrieved_at, denominator.freshness_retrieved_at)
            if f is not None
        ]
        derived_freshness: str | None = (
            max(freshness_values) if freshness_values else None
        )
        if numerator.value_decimal is None or denominator.value_decimal is None:
            value, reason = None, "source_not_available"
        elif denominator.value_decimal == 0:
            value, reason = None, "zero_denominator"
        else:
            value = numerator.value_decimal / denominator.value_decimal * scale
            reason = None
        derived.append(
            _metric(
                template=template,
                canonical_metric=canonical,
                value=value,
                reason=reason,
                currency=numerator.currency if is_money and value is not None else None,
                source_ids=source_ids,
                freshness=derived_freshness,
                calculated_at=calculated_at,
            )
        )

    ordered = [base[name] for name in _BASE_METRICS if name in base]
    return tuple(ordered + derived)
