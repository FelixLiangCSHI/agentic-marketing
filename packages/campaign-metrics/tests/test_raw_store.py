"""Raw metric store: append-only, hash-deduped, immutable."""

from __future__ import annotations

import pytest
from builders import make_raw

from campaign_metrics.models import RawImmutableError
from campaign_metrics.stores import FakeRawMetricStore


def test_append_inserts_new_record() -> None:
    store = FakeRawMetricStore()
    assert store.append(make_raw()) == "inserted"
    assert len(store.records()) == 1


def test_duplicate_pull_is_deduped_by_source_hash() -> None:
    store = FakeRawMetricStore()
    store.append(make_raw(metric_id="raw-0001"))
    outcome = store.append(make_raw(metric_id="raw-9999"))
    assert outcome == "duplicate"
    assert len(store.records()) == 1


def test_provider_revision_is_a_new_row_not_an_update() -> None:
    store = FakeRawMetricStore()
    store.append(make_raw(metric_id="raw-0001", provider_value=12450))
    outcome = store.append(
        make_raw(
            metric_id="raw-0002",
            provider_value=12000,
            source_response_hash="sha256:" + "b" * 64,
            retrieved_at="2026-09-15T00:00:00Z",
        )
    )
    assert outcome == "inserted"
    values = [r.provider_value for r in store.records()]
    assert values == [12450, 12000]


def test_raw_records_cannot_be_mutated() -> None:
    store = FakeRawMetricStore()
    store.append(make_raw())
    record = store.records()[0]
    with pytest.raises(Exception):
        record.provider_value = 0


def test_store_has_no_update_or_delete_api() -> None:
    store = FakeRawMetricStore()
    assert not hasattr(store, "update")
    assert not hasattr(store, "delete")


def test_same_metric_id_with_different_content_is_rejected() -> None:
    store = FakeRawMetricStore()
    store.append(make_raw(metric_id="raw-0001"))
    with pytest.raises(RawImmutableError):
        store.append(
            make_raw(
                metric_id="raw-0001",
                provider_value=99,
                source_response_hash="sha256:" + "c" * 64,
            )
        )


def test_missing_value_is_preserved_not_zero() -> None:
    store = FakeRawMetricStore()
    store.append(
        make_raw(
            provider_field_name="conversions",
            provider_value=None,
            provider_value_type="missing",
        )
    )
    record = store.records()[0]
    assert record.provider_value is None
    assert record.provider_value_type == "missing"


def test_true_zero_is_preserved_as_zero() -> None:
    store = FakeRawMetricStore()
    store.append(make_raw(provider_field_name="clicks", provider_value=0))
    assert store.records()[0].provider_value == 0


def test_rows_for_filters_by_channel_and_object() -> None:
    store = FakeRawMetricStore()
    store.append(make_raw(metric_id="raw-0001"))
    store.append(
        make_raw(
            metric_id="raw-0002",
            channel="google_ads",
            external_object_id="customers/1/campaigns/9",
            source_response_hash="sha256:" + "d" * 64,
        )
    )
    rows = store.rows_for(channel="linkedin", external_object_id="urn:li:sponsoredCampaign:1001")
    assert [r.metric_id for r in rows] == ["raw-0001"]


def test_tenant_isolation() -> None:
    store = FakeRawMetricStore()
    store.append(make_raw(metric_id="raw-0001", tenant_id="tenant-a"))
    store.append(
        make_raw(
            metric_id="raw-0002",
            tenant_id="tenant-b",
            source_response_hash="sha256:" + "e" * 64,
        )
    )
    rows = store.rows_for(
        channel="linkedin",
        external_object_id="urn:li:sponsoredCampaign:1001",
        tenant_id="tenant-a",
    )
    assert [r.metric_id for r in rows] == ["raw-0001"]
