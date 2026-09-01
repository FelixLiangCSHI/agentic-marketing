"""Async media worker: durable-queue polling with restart resume.

Flow: ``submit`` persists the job record + enqueues a poll task, then
``process_once`` (called by any worker instance sharing the same store,
queue and transport) polls status, downloads, validates and imports the
asset. Polling is queue-driven with the queue's backoff redelivery — no
public webhook exists (``callback_webhook_enabled: false``).

Guarantees:
- Create is idempotent: duplicate submits with the same
  ``run_id_node_id_input_hash`` never create a second provider job.
- Create timeout reconciles by idempotency key first (``find_job``);
  only when the provider truly has no job does it retry the create.
- Unknown jobs stop the pipeline for that key: the record moves to
  ``NEEDS_RECONCILE`` and the message is nacked toward the DLQ for human
  reconciliation — never a fresh create.
- Worker restart resume: a new worker instance with the same store and
  queue continues exactly where the previous one stopped.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Protocol

from infra_core.queue import QueueClient
from jimeng_connector.contracts import (
    GeneratedAssetV1,
    JobRecordV1,
    MediaJobRequestV1,
    request_hash,
)
from jimeng_connector.errors import (
    CreateTimeoutError,
    JobCancelledError,
    JobFailedError,
    ProviderRateLimitedError,
    ResultUrlExpiredError,
    UnknownJobError,
)
from jimeng_connector.governance import MOCK_COST_PER_IMAGE, JobRateLimiter, MediaBudget
from jimeng_connector.storage import AssetImporter
from jimeng_connector.transport import MediaTransport, RateLimited, TransportTimeout

POLL_TOPIC = "jimeng.media.poll"


class JobStore(Protocol):
    """Persistent job records; survives worker restarts."""

    def save(self, record: JobRecordV1) -> None: ...

    def get(self, idempotency_key: str) -> JobRecordV1 | None: ...

    def put_if_absent(self, record: JobRecordV1) -> JobRecordV1: ...

    def save_request(self, idempotency_key: str, request: MediaJobRequestV1) -> None: ...

    def get_request(self, idempotency_key: str) -> MediaJobRequestV1 | None: ...


@dataclass
class InMemoryJobStore:
    """In-memory store with persistent-store semantics for tests/local."""

    _records: dict[str, JobRecordV1] = field(default_factory=dict)
    _requests: dict[str, MediaJobRequestV1] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def save(self, record: JobRecordV1) -> None:
        self._records[record.idempotency_key] = record

    def get(self, idempotency_key: str) -> JobRecordV1 | None:
        return self._records.get(idempotency_key)

    def put_if_absent(self, record: JobRecordV1) -> JobRecordV1:
        """Atomic claim: returns the stored record (existing wins the race)."""
        with self._lock:
            existing = self._records.get(record.idempotency_key)
            if existing is not None:
                return existing
            self._records[record.idempotency_key] = record
            return record

    def save_request(self, idempotency_key: str, request: MediaJobRequestV1) -> None:
        self._requests[idempotency_key] = request

    def get_request(self, idempotency_key: str) -> MediaJobRequestV1 | None:
        return self._requests.get(idempotency_key)


@dataclass
class JimengMediaWorker:
    """Submits jobs and processes queue-driven poll tasks."""

    transport: MediaTransport
    store: JobStore
    queue: QueueClient
    importer: AssetImporter
    limiter: JobRateLimiter
    budget: MediaBudget
    model_id: str
    config_hash: str
    max_polls: int = 200

    # -- submit --------------------------------------------------------
    def submit(self, request: MediaJobRequestV1) -> JobRecordV1:
        key = request.idempotency_key()
        existing = self.store.get(key)
        if existing is not None:
            return existing  # duplicate submit: no second provider job
        estimated = MOCK_COST_PER_IMAGE * request.image_count
        self.budget.check_before_create(estimated)
        self.limiter.acquire_create()
        try:
            record = JobRecordV1(
                idempotency_key=key,
                request_hash=request_hash(
                    request, model_id=self.model_id, config_hash=self.config_hash
                ),
                state="PENDING",
            )
            self.store.save_request(key, request)
            claimed = self.store.put_if_absent(record)
            if claimed is not record:
                # Another worker won the atomic claim: it owns the provider
                # job and the poll task; never create a second provider job.
                return claimed
            record = self._create_with_reconcile(request, record)
        finally:
            self.limiter.release()
        self.queue.enqueue(POLL_TOPIC, {"idempotency_key": key}, idempotency_key=key)
        return record

    def _create_with_reconcile(
        self, request: MediaJobRequestV1, record: JobRecordV1
    ) -> JobRecordV1:
        key = record.idempotency_key
        try:
            job = self.transport.create_job(request, idempotency_key=key)
        except TransportTimeout:
            # 创建超时:先按 idempotency 对账，绝不直接重复创建。
            found = self.transport.find_job(idempotency_key=key)
            if found is None:
                record.state = "NEEDS_RECONCILE"
                record.error_code = "create_timeout"
                self.store.save(record)
                raise CreateTimeoutError(
                    "create timed out and reconcile found no job; manual reconcile"
                ) from None
            job = found
        except RateLimited as exc:
            record.state = "NEEDS_RECONCILE"
            record.error_code = "rate_limited"
            self.store.save(record)
            raise ProviderRateLimitedError(
                f"provider rate limited the create (retry after {exc.retry_after_s}s)"
            ) from exc
        record.provider_job_id = job.provider_job_id
        record.state = "CREATED"
        record.error_code = None
        self.store.save(record)
        return record

    # -- poll ----------------------------------------------------------
    def process_once(self, *, worker_id: str) -> JobRecordV1 | None:
        """Handle at most one poll message; returns the updated record."""
        message = self.queue.receive(POLL_TOPIC, worker_id=worker_id)
        if message is None:
            return None
        key = str(message.payload["idempotency_key"])
        record = self.store.get(key)
        request = self.store.get_request(key)
        if record is None or request is None or record.provider_job_id is None:
            self.queue.nack(message, reason="job record missing; needs reconcile")
            return None
        try:
            status = self.transport.get_status(record.provider_job_id)
        except UnknownJobError:
            record.state = "NEEDS_RECONCILE"
            record.error_code = "unknown_job"
            self.store.save(record)
            # 未知 Job：停止创建，交由人工对账/DLQ；绝不重新创建。
            self.queue.nack(message, reason="unknown provider job; human reconcile")
            return record
        record.polls += 1
        if status.state == "running":
            if record.polls >= self.max_polls:
                record.state = "FAILED"
                record.error_code = "poll_deadline_exceeded"
                self.store.save(record)
                self.queue.ack(message)
                return record
            record.state = "RUNNING"
            self.store.save(record)
            self.queue.nack(message, reason="job still running; poll again")
            return record
        if status.state == "failed":
            record.state = "FAILED"
            record.error_code = status.failure_code or "provider_job_failed"
            self.store.save(record)
            self.queue.ack(message)
            return record
        if status.state == "cancelled":
            record.state = "CANCELLED"
            record.error_code = "job_cancelled"
            self.store.save(record)
            self.queue.ack(message)
            return record
        # completed -> download, validate, import
        try:
            asset = self._download_and_import(request, record)
        except ResultUrlExpiredError:
            # 临时 URL 过期:重新取 result 引用重试下载，不重建 Job。
            self.queue.nack(message, reason="result URL expired; re-fetching")
            return record
        record.state = "COMPLETED"
        record.asset_object_key = asset.object_key
        record.asset_object_version = asset.object_version
        record.asset_sha256 = asset.sha256
        self.store.save(record)
        self.budget.record_asset(MOCK_COST_PER_IMAGE * request.image_count)
        self.queue.ack(message)
        return record

    def _download_and_import(
        self, request: MediaJobRequestV1, record: JobRecordV1
    ) -> GeneratedAssetV1:
        assert record.provider_job_id is not None
        result = self.transport.get_result(record.provider_job_id)
        downloaded = self.transport.download(result)
        return self.importer.import_generated(request, result, downloaded)

    # -- cancel --------------------------------------------------------
    def cancel(self, idempotency_key: str) -> JobRecordV1:
        record = self.store.get(idempotency_key)
        if record is None:
            raise UnknownJobError(f"no job record for {idempotency_key}")
        if record.state in ("COMPLETED", "FAILED", "CANCELLED"):
            return record
        if record.provider_job_id is not None:
            self.transport.cancel_job(record.provider_job_id)
        self.queue.cancel(POLL_TOPIC, idempotency_key=idempotency_key)
        record.state = "CANCELLED"
        record.error_code = "job_cancelled"
        self.store.save(record)
        return record

    # -- helpers -------------------------------------------------------
    def raise_for_terminal_failure(self, record: JobRecordV1) -> None:
        if record.state == "FAILED":
            raise JobFailedError(f"provider job failed: {record.error_code}")
        if record.state == "CANCELLED":
            raise JobCancelledError("job was cancelled")
