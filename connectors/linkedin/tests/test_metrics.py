"""RED tests: Ads Reporting metrics reads with cursor pagination.

Raw provider fields are preserved verbatim with retrieval metadata and a
source-response hash; missing values stay missing (never coerced to 0);
pagination follows an explicit cursor until exhausted.
"""

from __future__ import annotations

from linkedin_connector import MetricsPage, fetch_metrics_page

from builders import make_config


WINDOW = {"start": "2026-09-21T00:00:00Z", "end": "2026-09-28T00:00:00Z"}


def test_first_page_returns_rows_and_cursor() -> None:
    page = fetch_metrics_page(
        config=make_config(),
        account_id="acct-linkedin-dev",
        external_object_id="urn:li:sponsoredCampaign:31014001",
        window=WINDOW,
        cursor=None,
        retrieved_at="2026-09-28T01:00:00Z",
    )
    assert isinstance(page, MetricsPage)
    assert page.rows
    assert page.next_cursor is not None


def test_pagination_terminates_and_rows_are_deterministic() -> None:
    config = make_config()
    cursor: str | None = None
    all_rows: list[dict[str, object]] = []
    for _ in range(10):
        page = fetch_metrics_page(
            config=config,
            account_id="acct-linkedin-dev",
            external_object_id="urn:li:sponsoredCampaign:31014001",
            window=WINDOW,
            cursor=cursor,
            retrieved_at="2026-09-28T01:00:00Z",
        )
        all_rows.extend(dict(row.provider_fields) for row in page.rows)
        cursor = page.next_cursor
        if cursor is None:
            break
    assert cursor is None
    assert len(all_rows) >= 3
    # deterministic across a second full read
    again: list[dict[str, object]] = []
    cursor = None
    while True:
        page = fetch_metrics_page(
            config=config,
            account_id="acct-linkedin-dev",
            external_object_id="urn:li:sponsoredCampaign:31014001",
            window=WINDOW,
            cursor=cursor,
            retrieved_at="2026-09-28T01:00:00Z",
        )
        again.extend(dict(row.provider_fields) for row in page.rows)
        cursor = page.next_cursor
        if cursor is None:
            break
    assert all_rows == again


def test_rows_preserve_raw_fields_and_metadata() -> None:
    page = fetch_metrics_page(
        config=make_config(),
        account_id="acct-linkedin-dev",
        external_object_id="urn:li:sponsoredCampaign:31014001",
        window=WINDOW,
        cursor=None,
        retrieved_at="2026-09-28T01:00:00Z",
    )
    row = page.rows[0]
    assert row.provider_field_name
    assert row.retrieved_at == "2026-09-28T01:00:00Z"
    assert row.source_response_hash.startswith("sha256:")
    assert row.period_start == WINDOW["start"]
    assert row.period_end == WINDOW["end"]


def test_missing_values_stay_missing_not_zero() -> None:
    config = make_config()
    cursor: str | None = None
    values: dict[str, object] = {}
    while True:
        page = fetch_metrics_page(
            config=config,
            account_id="acct-linkedin-dev",
            external_object_id="urn:li:sponsoredCampaign:31014001",
            window=WINDOW,
            cursor=cursor,
            retrieved_at="2026-09-28T01:00:00Z",
        )
        for row in page.rows:
            values[row.provider_field_name] = row.provider_value
        cursor = page.next_cursor
        if cursor is None:
            break
    assert values["conversions"] is None  # provider did not report -> stays missing
    assert values["clicks"] == 0  # a true zero stays zero
