"""Metrics ingest: cursor pagination with persisted watermark/checkpoint.

The ingestor persists the checkpoint after every page so a worker
restart resumes exactly where pagination stopped; raw rows are deduped
by source-response hash so duplicate pulls insert nothing new.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from campaign_metrics.models import IngestCheckpoint, IngestContext, RawMetricRecord
from campaign_metrics.stores import RawMetricStore, WatermarkStore


@dataclass(frozen=True)
class ProviderRow:
    """One provider field/value pair exactly as returned by the channel."""

    field_name: str
    value: object | None
    value_type: str


@dataclass(frozen=True)
class ProviderPage:
    """One page of provider rows plus the next cursor (None = done)."""

    rows: tuple[ProviderRow, ...]
    next_cursor: str | None
    source_response_hash: str
    retrieved_at: str


class PageFetcher(Protocol):
    def fetch(self, cursor: str | None) -> ProviderPage: ...


@dataclass(frozen=True)
class IngestResult:
    inserted: int
    duplicates: int


def _record_id(context: IngestContext, page: ProviderPage, row: ProviderRow) -> str:
    digest = page.source_response_hash.removeprefix("sha256:")[:16]
    return (
        f"raw-{context.channel}-{context.external_object_id}"
        f"-{row.field_name}-{context.period_start}-{digest}"
    )


class MetricsIngestor:
    """Pull raw metric pages into the append-only store with checkpoints."""

    def __init__(self, *, raw_store: RawMetricStore, watermark_store: WatermarkStore) -> None:
        self._raw_store = raw_store
        self._watermark_store = watermark_store

    def run(self, *, context: IngestContext, fetcher: PageFetcher) -> IngestResult:
        key = context.stream_key()
        checkpoint = self._watermark_store.get(key)
        cursor: str | None = None
        if checkpoint is not None and not checkpoint.completed:
            cursor = checkpoint.cursor
        inserted = 0
        duplicates = 0
        while True:
            page = fetcher.fetch(cursor)
            for row in page.rows:
                record = RawMetricRecord(
                    metric_id=_record_id(context, page, row),
                    tenant_id=context.tenant_id,
                    channel=context.channel,
                    account_id=context.account_id,
                    external_object_id=context.external_object_id,
                    provider_field_name=row.field_name,
                    provider_value=row.value,
                    provider_value_type=row.value_type,
                    provider_currency=context.provider_currency,
                    provider_timezone=context.provider_timezone,
                    attribution_window=context.attribution_window,
                    period_start=context.period_start,
                    period_end=context.period_end,
                    provider_api_version=context.provider_api_version,
                    retrieved_at=page.retrieved_at,
                    source_response_ref=context.source_response_ref,
                    source_response_hash=page.source_response_hash,
                    connector_version=context.connector_version,
                    trace_id=context.trace_id,
                )
                if self._raw_store.append(record) == "inserted":
                    inserted += 1
                else:
                    duplicates += 1
            cursor = page.next_cursor
            self._watermark_store.set(
                key,
                IngestCheckpoint(
                    cursor=cursor,
                    watermark=page.retrieved_at,
                    completed=cursor is None,
                ),
            )
            if cursor is None:
                return IngestResult(inserted=inserted, duplicates=duplicates)
