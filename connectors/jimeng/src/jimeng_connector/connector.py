"""Unified Jimeng connector.

Interface (per the connector SDK contract): ``validate_config / dry_run /
execute / get_status / reconcile / cancel / normalize_error``. Image
generation is an async job, so all job actions are supported (unlike the
synchronous DeepSeek chat connector). Video capability is NOT claimed:
requesting anything but images is a typed ``NotSupportedError``.

mock mode never performs external HTTP; sandbox/live require enabled
config, fully resolved runtime settings and a recorded approval evidence
reference, otherwise a typed ``RealModeBlockedError``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from infra_core.clock import Clock, SystemClock
from infra_core.objectstore import ObjectStore
from infra_core.queue import QueueClient
from jimeng_connector.config import JimengConfig, RuntimeSettings, resolve_runtime
from jimeng_connector.contracts import JobRecordV1, MediaJobRequestV1, request_hash
from jimeng_connector.errors import (
    ConnectorErrorV1,
    JimengConnectorError,
    NotSupportedError,
    RealModeBlockedError,
    RequestInvalidError,
    UnknownJobError,
)
from jimeng_connector.governance import MOCK_COST_PER_IMAGE, JobRateLimiter, MediaBudget
from jimeng_connector.storage import AssetImporter
from jimeng_connector.transport import MediaTransport
from jimeng_connector.worker import InMemoryJobStore, JimengMediaWorker, JobStore


@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    mode: str
    enabled: bool
    config_hash: str
    checks: tuple[str, ...]


@dataclass(frozen=True)
class DryRunReport:
    ok: bool
    request_hash: str
    idempotency_key: str
    model_id: str
    estimated_cost: float


class JimengConnector:
    """One configured Jimeng media connector instance."""

    connector_kind = "jimeng"

    def __init__(
        self,
        config: JimengConfig,
        *,
        env: Mapping[str, str],
        transport: MediaTransport,
        queue: QueueClient,
        object_store: ObjectStore,
        environment: str,
        clock: Clock | None = None,
        job_store: JobStore | None = None,
        real_mode_approval_ref: str | None = None,
    ) -> None:
        self._config = config
        self._config_hash = config.config_hash()
        self._runtime: RuntimeSettings = resolve_runtime(config, env)
        if self._runtime.mode != "mock" and not real_mode_approval_ref:
            raise RealModeBlockedError(
                "sandbox/live require a recorded vendor/procurement approval "
                "reference; real path is BLOCKED"
            )
        clock = clock or SystemClock()
        self.budget = MediaBudget(
            per_run_budget=self._runtime.per_run_budget,
            daily_budget=self._runtime.daily_budget,
            max_assets_per_run=self._runtime.max_assets_per_run,
            alert_at_percent=config.cost_control.alert_at_percent,
        )
        self.worker = JimengMediaWorker(
            transport=transport,
            store=job_store or InMemoryJobStore(),
            queue=queue,
            importer=AssetImporter(store=object_store, environment=environment),
            limiter=JobRateLimiter(
                clock=clock,
                requests_per_minute=self._runtime.requests_per_minute,
                max_concurrency=self._runtime.max_concurrency,
                jobs_per_day=self._runtime.jobs_per_day,
            ),
            budget=self.budget,
            model_id=self._runtime.model_id,
            config_hash=self._config_hash,
        )
        self._clock = clock

    @property
    def runtime(self) -> RuntimeSettings:
        return self._runtime

    @property
    def config_hash(self) -> str:
        return self._config_hash

    # ------------------------------------------------------------------
    # Unified connector interface
    # ------------------------------------------------------------------
    def validate_config(self) -> ValidationReport:
        checks = (
            f"schema_version={self._config.schema_version}",
            f"mode={self._runtime.mode}",
            f"enabled={self._config.enabled}",
            f"tenant={self._runtime.tenant_variant}/{self._runtime.region}",
            "credentials=secretref-only",
            "cookie_auth=forbidden",
            "webhook=disabled",
            f"capability={self._config.model.capability}",
        )
        return ValidationReport(
            ok=True,
            mode=self._runtime.mode,
            enabled=self._config.enabled,
            config_hash=self._config_hash,
            checks=checks,
        )

    def dry_run(self, request: MediaJobRequestV1) -> DryRunReport:
        """Validate a request end-to-end without any transport call."""
        self._check_request(request)
        estimated = MOCK_COST_PER_IMAGE * request.image_count
        self.budget.check_before_create(estimated)
        return DryRunReport(
            ok=True,
            request_hash=request_hash(
                request, model_id=self._runtime.model_id, config_hash=self._config_hash
            ),
            idempotency_key=request.idempotency_key(),
            model_id=self._runtime.model_id,
            estimated_cost=estimated,
        )

    def execute(self, request: MediaJobRequestV1) -> JobRecordV1:
        """Create (or reconcile) the async job and enqueue polling."""
        self._check_request(request)
        return self.worker.submit(request)

    def get_status(self, idempotency_key: str) -> JobRecordV1:
        record = self.worker.store.get(idempotency_key)
        if record is None:
            raise UnknownJobError(f"no job record for {idempotency_key}")
        return record

    def reconcile(self, idempotency_key: str) -> JobRecordV1:
        """Adopt the provider-side job for a locally incomplete record."""
        record = self.worker.store.get(idempotency_key)
        if record is None:
            raise UnknownJobError(f"no job record for {idempotency_key}")
        found = self.worker.transport.find_job(idempotency_key=idempotency_key)
        if found is None:
            record.state = "NEEDS_RECONCILE"
            record.error_code = "unknown_job"
            self.worker.store.save(record)
            return record
        record.provider_job_id = found.provider_job_id
        if record.state in ("PENDING", "NEEDS_RECONCILE"):
            record.state = "CREATED"
            record.error_code = None
        self.worker.store.save(record)
        return record

    def cancel(self, idempotency_key: str) -> JobRecordV1:
        return self.worker.cancel(idempotency_key)

    def normalize_error(self, error: Exception, *, trace_id: str) -> ConnectorErrorV1:
        if isinstance(error, JimengConnectorError):
            code = error.code
            retryable = error.retryable
            message = str(error) or error.code
        else:
            code = "unexpected_error"
            retryable = False
            message = f"{type(error).__name__}: {error}"
        occurred = self._clock.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        return ConnectorErrorV1(
            connector="jimeng",
            code=code,
            message=message[:2000],
            trace_id=trace_id,
            retryable=retryable,
            details={"provider": "jimeng", "mode": self._runtime.mode},
            occurred_at=occurred,
        )

    # ------------------------------------------------------------------
    def _check_request(self, request: MediaJobRequestV1) -> None:
        if not isinstance(request, MediaJobRequestV1):
            raise RequestInvalidError("execute requires a MediaJobRequestV1")
        if request.output_format not in self._config.model.output_formats:
            raise NotSupportedError(
                f"output format {request.output_format!r} is not offered by the "
                "approved image model"
            )
        if request.image_count > self._runtime.max_images_per_request:
            raise RequestInvalidError(
                f"image_count exceeds max_images_per_request "
                f"({self._runtime.max_images_per_request})"
            )
