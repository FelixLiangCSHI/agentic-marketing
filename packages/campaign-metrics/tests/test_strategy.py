"""Strategy drafts: DRAFT-only, evidence-bound, zero write tools."""

from __future__ import annotations

from builders import FAKE_NOW, make_raw_set

import pytest

from campaign_metrics.normalize import normalize
from campaign_metrics.report import build_performance_report
from campaign_metrics.strategy import (
    StrategyEvidenceError,
    build_strategy_recommendation,
)


def _make_report() -> dict[str, object]:
    raw = make_raw_set(impressions=10000, clicks=200, spend="500.00")
    normalized = normalize(raw, calculated_at=FAKE_NOW)
    return build_performance_report(
        report_id="rpt_" + "a" * 24,
        tenant_id="tenant-a",
        run_id="run-p3-0006",
        campaign_id="urn:li:sponsoredCampaign:1001",
        channel="linkedin",
        account_id="acct-1",
        period_start="2026-09-07",
        period_end="2026-09-13",
        normalized_metrics=normalized,
        approved_budget_minor=100000,
        budget_currency="USD",
        generated_at=FAKE_NOW,
        trace_id="trace-p3-0006",
    )


def _recommendation(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "action_type": "budget_adjustment",
        "summary": "Increase daily budget by 10% based on efficient CPC.",
        "evidence_metrics": ["cpc", "ctr"],
        "expected_impact": "More clicks at the observed CPC of 2.50 USD.",
        "risk": "Spend increases before the next report window confirms CPC.",
        "confidence": 0.6,
        "next_step": "create_activation_request",
    }
    values.update(overrides)
    return values


def test_strategy_is_always_marked_draft() -> None:
    strategy = build_strategy_recommendation(
        strategy_id="str_" + "b" * 24,
        report=_make_report(),
        recommendations=[_recommendation()],
        generated_at=FAKE_NOW,
    )
    assert strategy["status"] == "DRAFT"
    assert strategy["schema_version"] == "1.0"
    assert strategy["report_id"] == "rpt_" + "a" * 24
    assert strategy["data_window"] == {"start": "2026-09-07", "end": "2026-09-13"}


def test_every_recommendation_is_bound_to_report_evidence() -> None:
    strategy = build_strategy_recommendation(
        strategy_id="str_" + "b" * 24,
        report=_make_report(),
        recommendations=[_recommendation()],
        generated_at=FAKE_NOW,
    )
    recommendations = strategy["recommendations"]
    assert isinstance(recommendations, list)
    for rec in recommendations:
        assert rec["evidence"], rec
        for evidence in rec["evidence"]:
            assert evidence["source_raw_metric_ids"]
            assert evidence["formula_version"]
        assert rec["risk"]
        assert 0.0 <= rec["confidence"] <= 1.0
        assert rec["next_step"] in ("create_activation_request", "manual_task")


def test_fabricated_evidence_is_rejected() -> None:
    with pytest.raises(StrategyEvidenceError):
        build_strategy_recommendation(
            strategy_id="str_" + "b" * 24,
            report=_make_report(),
            recommendations=[_recommendation(evidence_metrics=["roas"])],
            generated_at=FAKE_NOW,
        )


def test_not_available_metric_cannot_be_used_as_evidence() -> None:
    raw = make_raw_set()  # conversions missing -> conversion_rate not_available
    normalized = normalize(raw, calculated_at=FAKE_NOW)
    report = build_performance_report(
        report_id="rpt_" + "a" * 24,
        tenant_id="tenant-a",
        run_id="run-p3-0006",
        campaign_id="urn:li:sponsoredCampaign:1001",
        channel="linkedin",
        account_id="acct-1",
        period_start="2026-09-07",
        period_end="2026-09-13",
        normalized_metrics=normalized,
        approved_budget_minor=100000,
        budget_currency="USD",
        generated_at=FAKE_NOW,
        trace_id="trace-p3-0006",
    )
    with pytest.raises(StrategyEvidenceError):
        build_strategy_recommendation(
            strategy_id="str_" + "b" * 24,
            report=report,
            recommendations=[_recommendation(evidence_metrics=["conversion_rate"])],
            generated_at=FAKE_NOW,
        )


def test_recommendation_without_risk_or_confidence_is_rejected() -> None:
    with pytest.raises(StrategyEvidenceError):
        build_strategy_recommendation(
            strategy_id="str_" + "b" * 24,
            report=_make_report(),
            recommendations=[_recommendation(risk="")],
            generated_at=FAKE_NOW,
        )
    with pytest.raises(StrategyEvidenceError):
        build_strategy_recommendation(
            strategy_id="str_" + "b" * 24,
            report=_make_report(),
            recommendations=[_recommendation(confidence=1.5)],
            generated_at=FAKE_NOW,
        )


def test_strategy_module_has_no_channel_write_tools() -> None:
    """The strategy module must not import or expose any external write path."""
    import campaign_metrics.strategy as strategy_module

    source = open(strategy_module.__file__, encoding="utf-8").read()
    for forbidden in (
        "connector_sdk",
        "linkedin_connector",
        "google_ads_connector",
        "campaign_activation",
        "activate(",
        "external_write",
    ):
        assert forbidden not in source
    assert not hasattr(strategy_module, "execute")
    assert not hasattr(strategy_module, "apply")


def test_execution_intent_only_yields_new_activation_request_stub() -> None:
    strategy = build_strategy_recommendation(
        strategy_id="str_" + "b" * 24,
        report=_make_report(),
        recommendations=[_recommendation()],
        generated_at=FAKE_NOW,
    )
    recommendations = strategy["recommendations"]
    assert isinstance(recommendations, list)
    rec = recommendations[0]
    assert rec["next_step"] == "create_activation_request"
    assert rec["executed"] is False


def test_strategy_validates_against_frozen_contract() -> None:
    import json
    from pathlib import Path

    strategy = build_strategy_recommendation(
        strategy_id="str_" + "b" * 24,
        report=_make_report(),
        recommendations=[_recommendation()],
        generated_at=FAKE_NOW,
    )
    repo_root = Path(__file__).resolve().parents[3]
    schema_path = (
        repo_root
        / "packages"
        / "domain-contracts"
        / "schemas"
        / "strategy-recommendation.v1.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    required = set(schema["required"])
    assert required <= set(strategy.keys())
    assert schema["properties"]["status"]["const"] == "DRAFT"
