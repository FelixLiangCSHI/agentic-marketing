"""Read-only strategy drafts bound to report evidence.

This module has no channel write tools: it can only produce ``DRAFT``
documents. Any recommendation that requires execution results in a new
``ActivationRequest`` (created elsewhere, with fresh dry-run, approval
and input hash) or a manual task — never a direct campaign change.
"""

from __future__ import annotations

from typing import Any

from campaign_metrics.models import MetricsError

_ACTION_TYPES = (
    "budget_adjustment",
    "audience_adjustment",
    "creative_adjustment",
    "schedule_adjustment",
    "pause",
)
_NEXT_STEPS = ("create_activation_request", "manual_task")


class StrategyEvidenceError(MetricsError):
    """A recommendation is not backed by usable report evidence."""


def build_strategy_recommendation(
    *,
    strategy_id: str,
    report: dict[str, Any],
    recommendations: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    """Assemble a DRAFT strategy document (strategy-recommendation.v1)."""
    report_metrics: dict[str, dict[str, Any]] = {
        entry["canonical_metric"]: entry for entry in report["metrics"]
    }

    validated: list[dict[str, Any]] = []
    for rec in recommendations:
        action_type = rec["action_type"]
        if action_type not in _ACTION_TYPES:
            raise StrategyEvidenceError(f"unknown action_type {action_type!r}")
        next_step = rec["next_step"]
        if next_step not in _NEXT_STEPS:
            raise StrategyEvidenceError(f"unknown next_step {next_step!r}")
        summary = rec["summary"]
        risk = rec["risk"]
        if not summary or not risk:
            raise StrategyEvidenceError("summary and risk are required")
        confidence = rec["confidence"]
        if not isinstance(confidence, (int, float)) or not 0.0 <= confidence <= 1.0:
            raise StrategyEvidenceError("confidence must be within [0, 1]")
        evidence_names = rec["evidence_metrics"]
        if not evidence_names:
            raise StrategyEvidenceError("at least one evidence metric is required")
        evidence: list[dict[str, Any]] = []
        for name in evidence_names:
            entry = report_metrics.get(name)
            if entry is None:
                raise StrategyEvidenceError(
                    f"evidence metric {name!r} is not present in the report"
                )
            if entry["status"] != "ok":
                raise StrategyEvidenceError(
                    f"evidence metric {name!r} is {entry['status']} and cannot back a claim"
                )
            evidence.append(
                {
                    "canonical_metric": entry["canonical_metric"],
                    "value": entry["value"],
                    "source_raw_metric_ids": list(entry["source_raw_metric_ids"]),
                    "formula_version": entry["formula_version"],
                    "freshness_retrieved_at": entry["freshness_retrieved_at"],
                }
            )
        validated.append(
            {
                "action_type": action_type,
                "summary": summary,
                "evidence": evidence,
                "expected_impact": rec["expected_impact"],
                "risk": risk,
                "confidence": float(confidence),
                "next_step": next_step,
                "executed": False,
            }
        )

    return {
        "schema_version": "1.0",
        "strategy_id": strategy_id,
        "status": "DRAFT",
        "report_id": report["report_id"],
        "tenant_id": report["tenant_id"],
        "channel": report["channel"],
        "data_window": {
            "start": report["period_start"],
            "end": report["period_end"],
        },
        "recommendations": validated,
        "generated_at": generated_at,
        "trace_id": report["trace_id"],
    }
