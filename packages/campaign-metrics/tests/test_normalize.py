"""Normalization: Decimal, formula version, traceability, not_available."""

from __future__ import annotations

from decimal import Decimal

from builders import FAKE_NOW, make_raw, make_raw_set

from campaign_metrics.models import NormalizedMetric
from campaign_metrics.normalize import FORMULA_VERSION, normalize


def _by_metric(metrics: tuple[NormalizedMetric, ...]) -> dict[str, NormalizedMetric]:
    return {m.canonical_metric: m for m in metrics}


def test_base_metrics_are_decimal_and_traceable() -> None:
    raw = make_raw_set()
    result = _by_metric(normalize(raw, calculated_at=FAKE_NOW))
    impressions = result["impressions"]
    assert impressions.quality_status == "ok"
    assert impressions.value_decimal == Decimal("12450")
    assert impressions.formula_version == FORMULA_VERSION
    assert impressions.source_raw_metric_ids == ("raw-linkedin-0000",)
    spend = result["spend"]
    assert spend.value_decimal == Decimal("413.27")
    assert spend.currency == "USD"


def test_missing_never_becomes_zero() -> None:
    result = _by_metric(normalize(make_raw_set(), calculated_at=FAKE_NOW))
    conversions = result["conversions"]
    assert conversions.quality_status == "not_available"
    assert conversions.value_decimal is None
    assert conversions.not_available_reason == "provider_reported_missing"


def test_true_zero_stays_zero_with_ok_status() -> None:
    raw = make_raw_set(clicks=0)
    result = _by_metric(normalize(raw, calculated_at=FAKE_NOW))
    clicks = result["clicks"]
    assert clicks.quality_status == "ok"
    assert clicks.value_decimal == Decimal("0")


def test_ctr_matches_deterministic_engine_formula() -> None:
    """Compatibility with src/analysis: CTR = SUM(clicks) ÷ SUM(impressions)."""
    raw = make_raw_set(impressions=12450, clicks=311)
    result = _by_metric(normalize(raw, calculated_at=FAKE_NOW))
    ctr = result["ctr"]
    assert ctr.value_decimal == Decimal("311") / Decimal("12450")
    assert set(ctr.source_raw_metric_ids) == {
        "raw-linkedin-0000",
        "raw-linkedin-0001",
    }


def test_zero_denominator_is_not_available_like_engine() -> None:
    raw = make_raw_set(impressions=0, clicks=0)
    result = _by_metric(normalize(raw, calculated_at=FAKE_NOW))
    assert result["ctr"].quality_status == "not_available"
    assert result["ctr"].not_available_reason == "zero_denominator"


def test_derived_from_missing_source_is_not_available() -> None:
    result = _by_metric(normalize(make_raw_set(), calculated_at=FAKE_NOW))
    conversion_rate = result["conversion_rate"]
    assert conversion_rate.quality_status == "not_available"
    assert conversion_rate.not_available_reason == "source_not_available"


def test_cpc_and_cpm_formulas() -> None:
    raw = make_raw_set(impressions=10000, clicks=200, spend="500.00")
    result = _by_metric(normalize(raw, calculated_at=FAKE_NOW))
    assert result["cpc"].value_decimal == Decimal("2.50")
    assert result["cpm"].value_decimal == Decimal("50")


def test_google_cost_micros_converted_exactly() -> None:
    raw = make_raw_set(
        channel="google_ads", spend="413270000", spend_type="int64_string"
    )
    result = _by_metric(normalize(raw, calculated_at=FAKE_NOW))
    assert result["spend"].value_decimal == Decimal("413.27")


def test_unknown_currency_makes_spend_not_available() -> None:
    raw = make_raw_set(currency=None)
    result = _by_metric(normalize(raw, calculated_at=FAKE_NOW))
    spend = result["spend"]
    assert spend.quality_status == "not_available"
    assert spend.not_available_reason == "currency_unknown"


def test_currency_mismatch_is_not_available_not_guessed() -> None:
    raw = list(make_raw_set())
    raw.append(
        make_raw(
            metric_id="raw-linkedin-0099",
            provider_field_name="costInLocalCurrency",
            provider_value="100.00",
            provider_value_type="decimal_string",
            provider_currency="EUR",
            source_response_hash="sha256:" + "f" * 64,
        )
    )
    result = _by_metric(normalize(tuple(raw), calculated_at=FAKE_NOW))
    spend = result["spend"]
    assert spend.quality_status == "not_available"
    assert spend.not_available_reason == "currency_mismatch"


def test_timezone_mismatch_is_not_available() -> None:
    raw = list(make_raw_set())
    raw.append(
        make_raw(
            metric_id="raw-linkedin-0098",
            provider_field_name="impressions",
            provider_value=5,
            provider_timezone="America/Los_Angeles",
            source_response_hash="sha256:" + "9" * 64,
        )
    )
    result = _by_metric(normalize(tuple(raw), calculated_at=FAKE_NOW))
    impressions = result["impressions"]
    assert impressions.quality_status == "not_available"
    assert impressions.not_available_reason == "timezone_mismatch"


def test_attribution_window_mismatch_is_not_available() -> None:
    raw = list(make_raw_set())
    raw.append(
        make_raw(
            metric_id="raw-linkedin-0097",
            provider_field_name="clicks",
            provider_value=5,
            attribution_window="LAST_TOUCH_30D",
            source_response_hash="sha256:" + "8" * 64,
        )
    )
    result = _by_metric(normalize(tuple(raw), calculated_at=FAKE_NOW))
    clicks = result["clicks"]
    assert clicks.quality_status == "not_available"
    assert clicks.not_available_reason == "attribution_window_mismatch"


def test_duplicate_raw_values_from_revisions_use_latest_retrieval() -> None:
    raw = list(make_raw_set())
    raw.append(
        make_raw(
            metric_id="raw-linkedin-0096",
            provider_field_name="impressions",
            provider_value=13000,
            retrieved_at="2026-09-15T00:00:00Z",
            source_response_hash="sha256:" + "7" * 64,
        )
    )
    result = _by_metric(normalize(tuple(raw), calculated_at=FAKE_NOW))
    impressions = result["impressions"]
    assert impressions.value_decimal == Decimal("13000")
    assert impressions.source_raw_metric_ids == ("raw-linkedin-0096",)


def test_normalize_does_not_mutate_raw_records() -> None:
    raw = make_raw_set()
    before = [(r.metric_id, r.provider_value) for r in raw]
    normalize(raw, calculated_at=FAKE_NOW)
    normalize(raw, calculated_at="2026-09-15T00:00:00Z")
    assert [(r.metric_id, r.provider_value) for r in raw] == before


def test_recompute_is_deterministic() -> None:
    raw = make_raw_set()
    first = normalize(raw, calculated_at=FAKE_NOW)
    second = normalize(raw, calculated_at=FAKE_NOW)
    assert first == second


def test_normalize_rejects_mixed_tenant_account_object_or_window() -> None:
    import pytest

    from campaign_metrics.normalize import NormalizationInputError

    base = make_raw_set()
    for overrides in (
        {"tenant_id": "tenant-b"},
        {"account_id": "acct-2"},
        {"external_object_id": "urn:li:sponsoredCampaign:9999"},
        {"period_start": "2026-08-01"},
        {"period_end": "2026-08-31"},
    ):
        stray = make_raw(
            metric_id="raw-stray",
            source_response_hash="sha256:" + "f" * 64,
            **overrides,
        )
        with pytest.raises(NormalizationInputError):
            normalize(base + (stray,), calculated_at=FAKE_NOW)


def test_metric_id_carries_tenant_and_account() -> None:
    result = normalize(make_raw_set(), calculated_at=FAKE_NOW)
    assert all("tenant-a" in m.metric_id and "acct-1" in m.metric_id for m in result)
