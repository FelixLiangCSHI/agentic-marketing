"""Read-only performance report: every number is traceable or absent.

Each metric entry cites its source raw metric IDs, formula version and
freshness. Inference is never written as fact: metrics that cannot be
computed reliably appear as ``not_available`` with an explicit reason.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from campaign_metrics.models import MetricsError, NormalizedMetric


class ReportInputError(MetricsError):
    """The report inputs are inconsistent (wrong object, mixed windows)."""


def _format_value(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _budget_section(
    *,
    metrics_by_name: dict[str, NormalizedMetric],
    approved_budget_minor: int,
    budget_currency: str,
    has_metrics: bool,
) -> dict[str, Any]:
    not_available = {
        "approved_limit_minor": approved_budget_minor,
        "currency": budget_currency,
        "spend_minor": None,
        "variance_minor": None,
        "status": "not_available",
    }
    if not has_metrics:
        return {**not_available, "not_available_reason": "no_normalized_metrics"}
    spend = metrics_by_name.get("spend")
    if spend is None or spend.value_decimal is None:
        reason = spend.not_available_reason if spend is not None else "no_spend_metric"
        return {**not_available, "not_available_reason": reason}
    if spend.currency != budget_currency:
        return {**not_available, "not_available_reason": "currency_mismatch"}
    spend_minor_decimal = spend.value_decimal * 100
    if spend_minor_decimal != spend_minor_decimal.to_integral_value():
        return {**not_available, "not_available_reason": "sub_minor_precision"}
    spend_minor = int(spend_minor_decimal)
    return {
        "approved_limit_minor": approved_budget_minor,
        "currency": budget_currency,
        "spend_minor": spend_minor,
        "variance_minor": spend_minor - approved_budget_minor,
        "status": "ok",
        "not_available_reason": None,
    }


def build_performance_report(
    *,
    report_id: str,
    tenant_id: str,
    run_id: str,
    campaign_id: str,
    channel: str,
    account_id: str,
    period_start: str,
    period_end: str,
    normalized_metrics: tuple[NormalizedMetric, ...],
    approved_budget_minor: int,
    budget_currency: str,
    generated_at: str,
    trace_id: str,
) -> dict[str, Any]:
    """Assemble the read-only report document (performance-report.v1)."""
    for metric in normalized_metrics:
        if metric.external_object_id != campaign_id or metric.channel != channel:
            raise ReportInputError(
                f"metric {metric.metric_id!r} belongs to another object or channel"
            )
        if metric.tenant_id != tenant_id:
            raise ReportInputError(
                f"metric {metric.metric_id!r} belongs to another tenant"
            )
        if metric.period_start != period_start or metric.period_end != period_end:
            raise ReportInputError(
                f"metric {metric.metric_id!r} covers a different time window"
            )

    entries: list[dict[str, Any]] = []
    warnings: list[str] = []
    for metric in normalized_metrics:
        entries.append(
            {
                "canonical_metric": metric.canonical_metric,
                "value": (
                    _format_value(metric.value_decimal)
                    if metric.value_decimal is not None
                    else None
                ),
                "status": metric.quality_status,
                "not_available_reason": metric.not_available_reason,
                "currency": metric.currency,
                "source_raw_metric_ids": list(metric.source_raw_metric_ids),
                "formula_version": metric.formula_version,
                "freshness_retrieved_at": metric.freshness_retrieved_at,
            }
        )
        if metric.quality_status == "not_available":
            warnings.append(
                f"{metric.canonical_metric} not_available: {metric.not_available_reason}"
            )

    freshness_values = [
        m.freshness_retrieved_at
        for m in normalized_metrics
        if m.freshness_retrieved_at is not None
    ]
    metrics_by_name = {m.canonical_metric: m for m in normalized_metrics}
    return {
        "schema_version": "1.0",
        "report_id": report_id,
        "tenant_id": tenant_id,
        "run_id": run_id,
        "campaign_id": campaign_id,
        "channel": channel,
        "account_id": account_id,
        "period_start": period_start,
        "period_end": period_end,
        "data_freshness_at": max(freshness_values) if freshness_values else None,
        "metrics": entries,
        "budget": _budget_section(
            metrics_by_name=metrics_by_name,
            approved_budget_minor=approved_budget_minor,
            budget_currency=budget_currency,
            has_metrics=bool(normalized_metrics),
        ),
        "warnings": warnings,
        "generated_at": generated_at,
        "trace_id": trace_id,
    }
