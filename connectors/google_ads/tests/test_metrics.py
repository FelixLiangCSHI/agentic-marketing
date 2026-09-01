"""GAQL metrics tests: GoogleAdsService Search/SearchStream fixture pages,
raw fields preserved verbatim (missing never becomes 0), page-token cursor
pagination, per-page response hash, and resumable pagination interrupts."""

from __future__ import annotations

import pytest

from google_ads_connector import fetch_gaql_page

from builders import make_config

WINDOW = {"start": "2026-09-21", "end": "2026-09-27"}


class TestFetchGaqlPage:
    def test_first_page_has_rows_and_next_page_token(self) -> None:
        page = fetch_gaql_page(
            config=make_config(),
            customer_id_ref="config://accounts/dev/google_ads/customer-id",
            external_object_id="customers/synthetic/campaigns/1",
            window=WINDOW,
            page_token=None,
            retrieved_at="2026-09-28T00:00:00Z",
        )
        assert len(page.rows) > 0
        assert page.next_page_token == "page-2"
        first = page.rows[0]
        assert first.provider_field_name == "metrics.impressions"
        assert first.provider_value == 20831
        assert first.provider_value_type == "integer"
        assert first.source_response_hash.startswith("sha256:")
        assert first.gaql_query.startswith("SELECT")

    def test_missing_values_stay_missing(self) -> None:
        page = fetch_gaql_page(
            config=make_config(),
            customer_id_ref="config://accounts/dev/google_ads/customer-id",
            external_object_id="customers/synthetic/campaigns/1",
            window=WINDOW,
            page_token="page-2",
            retrieved_at="2026-09-28T00:00:00Z",
        )
        missing = [r for r in page.rows if r.provider_value_type == "missing"]
        assert missing, "fixture must include a missing metric"
        assert all(r.provider_value is None for r in missing)
        assert page.next_page_token is None

    def test_raw_micros_preserved_verbatim(self) -> None:
        page = fetch_gaql_page(
            config=make_config(),
            customer_id_ref="config://accounts/dev/google_ads/customer-id",
            external_object_id="customers/synthetic/campaigns/1",
            window=WINDOW,
            page_token="page-2",
            retrieved_at="2026-09-28T00:00:00Z",
        )
        micros = next(r for r in page.rows if r.provider_field_name == "metrics.cost_micros")
        assert micros.provider_value == "413270000"
        assert micros.provider_value_type == "int64_string"

    def test_page_hashes_differ_per_page(self) -> None:
        kwargs = dict(
            config=make_config(),
            customer_id_ref="config://accounts/dev/google_ads/customer-id",
            external_object_id="customers/synthetic/campaigns/1",
            window=WINDOW,
            retrieved_at="2026-09-28T00:00:00Z",
        )
        first = fetch_gaql_page(page_token=None, **kwargs)  # type: ignore[arg-type]
        second = fetch_gaql_page(page_token="page-2", **kwargs)  # type: ignore[arg-type]
        assert first.rows[0].source_response_hash != second.rows[0].source_response_hash

    def test_unknown_page_token_rejected(self) -> None:
        with pytest.raises(ValueError, match="page_token"):
            fetch_gaql_page(
                config=make_config(),
                customer_id_ref="config://accounts/dev/google_ads/customer-id",
                external_object_id="customers/synthetic/campaigns/1",
                window=WINDOW,
                page_token="page-999",
                retrieved_at="2026-09-28T00:00:00Z",
            )
