"""Ingest worker: watermark/cursor persistence, restart recovery, dedupe."""

from __future__ import annotations

import pytest
from builders import FAKE_NOW, Harness, make_context

from campaign_metrics.ingest import MetricsIngestor, ProviderPage, ProviderRow


def _pages() -> dict[str | None, ProviderPage]:
    return {
        None: ProviderPage(
            rows=(
                ProviderRow(field_name="impressions", value=12450, value_type="integer"),
                ProviderRow(field_name="clicks", value=0, value_type="integer"),
            ),
            next_cursor="page-2",
            source_response_hash="sha256:" + "1" * 64,
            retrieved_at=FAKE_NOW,
        ),
        "page-2": ProviderPage(
            rows=(
                ProviderRow(
                    field_name="costInLocalCurrency",
                    value="413.27",
                    value_type="decimal_string",
                ),
                ProviderRow(field_name="conversions", value=None, value_type="missing"),
            ),
            next_cursor=None,
            source_response_hash="sha256:" + "2" * 64,
            retrieved_at=FAKE_NOW,
        ),
    }


class FakeFetcher:
    def __init__(self, fail_on: str | None = "__never__") -> None:
        self.pages = _pages()
        self.fail_on = fail_on
        self.calls: list[str | None] = []

    def fetch(self, cursor: str | None) -> ProviderPage:
        self.calls.append(cursor)
        if cursor == self.fail_on:
            raise ConnectionError("simulated pagination interruption")
        return self.pages[cursor]


def test_full_ingest_stores_all_rows_and_completes_watermark() -> None:
    h = Harness()
    context = make_context()
    ingestor = MetricsIngestor(raw_store=h.raw_store, watermark_store=h.watermark_store)
    result = ingestor.run(context=context, fetcher=FakeFetcher())
    assert result.inserted == 4
    assert result.duplicates == 0
    checkpoint = h.watermark_store.get(context.stream_key())
    assert checkpoint is not None
    assert checkpoint.completed is True
    assert checkpoint.cursor is None
    assert checkpoint.watermark == FAKE_NOW


def test_duplicate_pull_inserts_nothing_new() -> None:
    h = Harness()
    context = make_context()
    ingestor = MetricsIngestor(raw_store=h.raw_store, watermark_store=h.watermark_store)
    ingestor.run(context=context, fetcher=FakeFetcher())
    second = ingestor.run(context=context, fetcher=FakeFetcher())
    assert second.inserted == 0
    assert second.duplicates == 4
    assert len(h.raw_store.records()) == 4


def test_pagination_interruption_persists_cursor() -> None:
    h = Harness()
    context = make_context()
    ingestor = MetricsIngestor(raw_store=h.raw_store, watermark_store=h.watermark_store)
    with pytest.raises(ConnectionError):
        ingestor.run(context=context, fetcher=FakeFetcher(fail_on="page-2"))
    checkpoint = h.watermark_store.get(context.stream_key())
    assert checkpoint is not None
    assert checkpoint.completed is False
    assert checkpoint.cursor == "page-2"
    assert len(h.raw_store.records()) == 2


def test_restart_resumes_from_cursor_without_duplicates() -> None:
    h = Harness()
    context = make_context()
    first = MetricsIngestor(raw_store=h.raw_store, watermark_store=h.watermark_store)
    with pytest.raises(ConnectionError):
        first.run(context=context, fetcher=FakeFetcher(fail_on="page-2"))

    restarted = MetricsIngestor(raw_store=h.raw_store, watermark_store=h.watermark_store)
    fetcher = FakeFetcher()
    result = restarted.run(context=context, fetcher=fetcher)
    assert fetcher.calls == ["page-2"]
    assert result.inserted == 2
    assert result.duplicates == 0
    assert len(h.raw_store.records()) == 4
    checkpoint = h.watermark_store.get(context.stream_key())
    assert checkpoint is not None and checkpoint.completed is True


def test_raw_rows_carry_full_provenance() -> None:
    h = Harness()
    context = make_context()
    MetricsIngestor(raw_store=h.raw_store, watermark_store=h.watermark_store).run(
        context=context, fetcher=FakeFetcher()
    )
    record = h.raw_store.records()[0]
    assert record.tenant_id == "tenant-a"
    assert record.channel == "linkedin"
    assert record.provider_field_name == "impressions"
    assert record.provider_value == 12450
    assert record.source_response_hash == "sha256:" + "1" * 64
    assert record.provider_api_version == "202409"
    assert record.connector_version == "linkedin-connector-0.1.0"
    assert record.trace_id == "trace-p3-0006"
    assert record.retrieved_at == FAKE_NOW


def test_missing_stays_missing_after_ingest() -> None:
    h = Harness()
    MetricsIngestor(raw_store=h.raw_store, watermark_store=h.watermark_store).run(
        context=make_context(), fetcher=FakeFetcher()
    )
    missing = [r for r in h.raw_store.records() if r.provider_field_name == "conversions"]
    assert missing[0].provider_value is None
    assert missing[0].provider_value_type == "missing"
    zero = [r for r in h.raw_store.records() if r.provider_field_name == "clicks"]
    assert zero[0].provider_value == 0


def test_separate_streams_keep_separate_watermarks() -> None:
    h = Harness()
    context_a = make_context()
    context_b = make_context(
        channel="google_ads", external_object_id="customers/1/campaigns/9"
    )
    ingestor = MetricsIngestor(raw_store=h.raw_store, watermark_store=h.watermark_store)
    ingestor.run(context=context_a, fetcher=FakeFetcher())
    assert h.watermark_store.get(context_b.stream_key()) is None


def test_linkedin_and_google_adapters_feed_the_ingestor() -> None:
    """Compatibility: the two channel metrics adapters plug into ingest."""
    from pathlib import Path

    from linkedin_connector.config import load_linkedin_config
    from linkedin_connector.metrics import fetch_metrics_page

    from campaign_metrics.adapters import linkedin_fetcher

    repo_root = Path(__file__).resolve().parents[3]
    config = load_linkedin_config(repo_root / "config" / "linkedin.yaml")
    h = Harness()
    context = make_context()
    fetcher = linkedin_fetcher(
        config=config,
        account_id=context.account_id,
        external_object_id=context.external_object_id,
        window={"start": context.period_start, "end": context.period_end},
        retrieved_at=FAKE_NOW,
        fetch_page=fetch_metrics_page,
    )
    result = MetricsIngestor(raw_store=h.raw_store, watermark_store=h.watermark_store).run(
        context=context, fetcher=fetcher
    )
    assert result.inserted == 4
    fields = {r.provider_field_name for r in h.raw_store.records()}
    assert fields == {"impressions", "clicks", "costInLocalCurrency", "conversions"}


def test_google_ads_adapter_feeds_the_ingestor() -> None:
    from pathlib import Path

    from google_ads_connector.config import load_google_ads_config
    from google_ads_connector.metrics import fetch_gaql_page

    from campaign_metrics.adapters import google_ads_fetcher

    repo_root = Path(__file__).resolve().parents[3]
    config = load_google_ads_config(repo_root / "config" / "google_ads.yaml")
    h = Harness()
    context = make_context(
        channel="google_ads", external_object_id="customers/1/campaigns/9"
    )
    fetcher = google_ads_fetcher(
        config=config,
        customer_id_ref=context.account_id,
        external_object_id=context.external_object_id,
        window={"start": context.period_start, "end": context.period_end},
        retrieved_at=FAKE_NOW,
        fetch_page=fetch_gaql_page,
    )
    result = MetricsIngestor(raw_store=h.raw_store, watermark_store=h.watermark_store).run(
        context=context, fetcher=fetcher
    )
    assert result.inserted == 4
    fields = {r.provider_field_name for r in h.raw_store.records()}
    assert "metrics.cost_micros" in fields
