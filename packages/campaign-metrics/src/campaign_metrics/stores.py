"""In-repo fake stores: append-only raw, versioned normalized, watermarks.

Real persistence lives in ``apps/api`` migration ``0005_raw_normalized_metrics``
(``campaign.raw_channel_metrics`` / ``campaign.normalized_metrics``). These
fakes enforce the same invariants for deterministic tests.
"""

from __future__ import annotations

from typing import Literal, Protocol

from campaign_metrics.models import (
    IngestCheckpoint,
    NormalizedMetric,
    RawImmutableError,
    RawMetricRecord,
)

AppendOutcome = Literal["inserted", "duplicate"]

StreamKey = tuple[str, str, str, str, str, str]


class RawMetricStore(Protocol):
    def append(self, record: RawMetricRecord) -> AppendOutcome: ...

    def records(self) -> tuple[RawMetricRecord, ...]: ...


class FakeRawMetricStore:
    """Append-only raw store deduped by the source-hash key.

    There is intentionally no update or delete API: provider revisions
    arrive as new rows with a new retrieval/hash.
    """

    def __init__(self) -> None:
        self._records: list[RawMetricRecord] = []
        self._by_dedupe_key: dict[tuple[str, str, str, str, str, str], RawMetricRecord] = {}
        self._by_metric_id: dict[str, RawMetricRecord] = {}

    def append(self, record: RawMetricRecord) -> AppendOutcome:
        existing = self._by_metric_id.get(record.metric_id)
        if existing is not None:
            if existing != record:
                raise RawImmutableError(
                    f"raw metric {record.metric_id!r} already exists with different content"
                )
            return "duplicate"
        if record.dedupe_key() in self._by_dedupe_key:
            return "duplicate"
        self._records.append(record)
        self._by_dedupe_key[record.dedupe_key()] = record
        self._by_metric_id[record.metric_id] = record
        return "inserted"

    def records(self) -> tuple[RawMetricRecord, ...]:
        return tuple(self._records)

    def rows_for(
        self,
        *,
        channel: str,
        external_object_id: str,
        tenant_id: str | None = None,
    ) -> tuple[RawMetricRecord, ...]:
        return tuple(
            record
            for record in self._records
            if record.channel == channel
            and record.external_object_id == external_object_id
            and (tenant_id is None or record.tenant_id == tenant_id)
        )


class NormalizedMetricStore(Protocol):
    def put(self, metric: NormalizedMetric) -> None: ...

    def records(self) -> tuple[NormalizedMetric, ...]: ...


class FakeNormalizedMetricStore:
    """Versioned normalized store; recomputation appends, never mutates raw."""

    def __init__(self) -> None:
        self._records: list[NormalizedMetric] = []

    def put(self, metric: NormalizedMetric) -> None:
        self._records.append(metric)

    def records(self) -> tuple[NormalizedMetric, ...]:
        return tuple(self._records)


class WatermarkStore(Protocol):
    def get(self, key: StreamKey) -> IngestCheckpoint | None: ...

    def set(self, key: StreamKey, checkpoint: IngestCheckpoint) -> None: ...


class FakeWatermarkStore:
    def __init__(self) -> None:
        self._checkpoints: dict[StreamKey, IngestCheckpoint] = {}

    def get(self, key: StreamKey) -> IngestCheckpoint | None:
        return self._checkpoints.get(key)

    def set(self, key: StreamKey, checkpoint: IngestCheckpoint) -> None:
        self._checkpoints[key] = checkpoint
