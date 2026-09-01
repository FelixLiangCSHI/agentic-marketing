"""Performance report: every number cites raw IDs, formula and freshness."""

from __future__ import annotations

from typing import Any

from builders import FAKE_NOW, make_raw_set

import pytest

from campaign_metrics.normalize import FORMULA_VERSION, normalize
from campaign_metrics.report import ReportInputError, build_performance_report


def _report(**overrides: object) -> dict[str, Any]:
    raw = make_raw_set()
    normalized = normalize(raw, calculated_at=FAKE_NOW)
    values: dict[str, object] = {
        "report_id": "rpt_" + "a" * 24,
        "tenant_id": "tenant-a",
        "run_id": "run-p3-0006",
        "campaign_id": "urn:li:sponsoredCampaign:1001",
        "channel": "linkedin",
        "account_id": "acct-1",
        "period_start": "2026-09-07",
        "period_end": "2026-09-13",
        "normalized_metrics": normalized,
        "approved_budget_minor": 100000,
        "budget_currency": "USD",
        "generated_at": FAKE_NOW,
        "trace_id": "trace-p3-0006",
    }
    values.update(overrides)
    return build_performance_report(**values)  # type: ignore[arg-type]


def test_report_metrics_cite_raw_ids_formula_and_freshness() -> None:
    report = _report()
    entries = report["metrics"]
    assert isinstance(entries, list) and entries
    for entry in entries:
        assert entry["formula_version"] == FORMULA_VERSION
        if entry["status"] == "ok":
            assert entry["source_raw_metric_ids"], entry
            assert entry["value"] is not None
            assert entry["freshness_retrieved_at"]
        else:
            assert entry["status"] == "not_available"
            assert entry["value"] is None
            assert entry["not_available_reason"]


def test_missing_metric_is_reported_not_available_with_reason() -> None:
    report = _report()
    metrics = {e["canonical_metric"]: e for e in report["metrics"]}
    assert metrics["conversions"]["status"] == "not_available"
    assert metrics["conversions"]["not_available_reason"] == "provider_reported_missing"
    assert metrics["conversions"]["value"] is None


def test_report_values_match_deterministic_computation_exactly() -> None:
    raw = make_raw_set(impressions=10000, clicks=200, spend="500.00")
    normalized = normalize(raw, calculated_at=FAKE_NOW)
    report = _report(normalized_metrics=normalized)
    metrics = {e["canonical_metric"]: e for e in report["metrics"]}
    assert metrics["ctr"]["value"] == "0.02"
    assert metrics["cpc"]["value"] == "2.5"
    assert metrics["cpm"]["value"] == "50"
    assert metrics["spend"]["value"] == "500"


def test_budget_variance_uses_approved_limit() -> None:
    raw = make_raw_set(spend="500.00")
    normalized = normalize(raw, calculated_at=FAKE_NOW)
    report = _report(normalized_metrics=normalized, approved_budget_minor=100000)
    budget = report["budget"]
    assert budget["approved_limit_minor"] == 100000
    assert budget["spend_minor"] == 50000
    assert budget["variance_minor"] == -50000
    assert budget["status"] == "ok"


def test_budget_is_not_available_when_spend_is_not_available() -> None:
    raw = make_raw_set(currency=None)
    normalized = normalize(raw, calculated_at=FAKE_NOW)
    report = _report(normalized_metrics=normalized)
    budget = report["budget"]
    assert budget["status"] == "not_available"
    assert budget["spend_minor"] is None


def test_budget_currency_mismatch_is_not_available() -> None:
    report = _report(budget_currency="EUR")
    assert report["budget"]["status"] == "not_available"
    assert report["budget"]["not_available_reason"] == "currency_mismatch"


def test_report_carries_identity_window_and_freshness() -> None:
    report = _report()
    assert report["schema_version"] == "1.0"
    assert report["report_id"].startswith("rpt_")
    assert report["channel"] == "linkedin"
    assert report["period_start"] == "2026-09-07"
    assert report["data_freshness_at"] == FAKE_NOW
    assert report["trace_id"] == "trace-p3-0006"


def test_report_rejects_metrics_from_other_objects() -> None:
    raw = make_raw_set()
    normalized = normalize(raw, calculated_at=FAKE_NOW)
    with pytest.raises(ReportInputError):
        _report(normalized_metrics=normalized, campaign_id="other-object")


def test_report_never_fabricates_numbers_for_empty_input() -> None:
    report = _report(normalized_metrics=())
    assert report["metrics"] == []
    assert report["budget"]["status"] == "not_available"
    assert report["budget"]["not_available_reason"] == "no_normalized_metrics"


def test_report_validates_against_frozen_contract() -> None:
    import json
    from pathlib import Path

    report = _report()
    repo_root = Path(__file__).resolve().parents[3]
    schema_path = (
        repo_root
        / "packages"
        / "domain-contracts"
        / "schemas"
        / "performance-report.v1.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    required = set(schema["required"])
    assert required <= set(report.keys())
    assert schema["properties"]["schema_version"]["const"] == report["schema_version"]


def test_report_rejects_metrics_from_other_tenant() -> None:
    with pytest.raises(ReportInputError):
        _report(tenant_id="tenant-b")


def test_report_rejects_metrics_from_other_time_window() -> None:
    with pytest.raises(ReportInputError):
        _report(period_start="2026-08-01")
    with pytest.raises(ReportInputError):
        _report(period_end="2026-09-30")
