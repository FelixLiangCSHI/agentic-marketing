"""Connector/async-worker tests: idempotency (100×), restart/resume,
create-timeout reconcile, URL expiry, object versioning, unknown job DLQ,
MIME/malware/cost security and error normalization.

All scenarios are deterministic mocks — no external HTTP anywhere.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from infra_core.clock import FakeClock
from infra_core.objectstore import FakeObjectStore, ObjectKey
from infra_core.queue import FakeQueueClient, RetryPolicy
from jimeng_connector import (
    POLL_TOPIC,
    BudgetExceededError,
    ConnectorErrorV1,
    InMemoryJobStore,
    JimengConnector,
    JimengMockTransport,
    LocalQueueFullError,
    MediaJobRequestV1,
    NotSupportedError,
    ProviderRateLimitedError,
    RealModeBlockedError,
    UnknownJobError,
    load_config,
)
from jimeng_connector.governance import JobRateLimiter, MediaBudget
from jimeng_connector.transport import MockScenario

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / "config" / "jimeng.yaml"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "jimeng"


def _clock() -> FakeClock:
    return FakeClock(datetime(2026, 8, 28, tzinfo=timezone.utc))


def _request(**overrides: object) -> MediaJobRequestV1:
    base: dict[str, object] = {
        "request_id": "req-0001",
        "run_id": "run-0001",
        "node_id": "generate-media",
        "tenant": "tenant-cshi",
        "prompt": "Product Alpha dosing visual, professional, clean",
        "output_format": "png",
        "image_count": 1,
    }
    base.update(overrides)
    return MediaJobRequestV1.model_validate(base)


def _connector(
    scenario: MockScenario = "completed",
    *,
    env: dict[str, str] | None = None,
    clock: FakeClock | None = None,
    transport: JimengMockTransport | None = None,
    store: InMemoryJobStore | None = None,
    queue: FakeQueueClient | None = None,
    object_store: FakeObjectStore | None = None,
) -> JimengConnector:
    clock = clock or _clock()
    return JimengConnector(
        load_config(CONFIG_PATH),
        env=env or {},
        transport=transport or JimengMockTransport(FIXTURES, scenario=scenario),
        queue=queue
        or FakeQueueClient(
            clock=clock,
            retry_policy=RetryPolicy(
                max_attempts=5,
                base_delay_seconds=1.0,
                max_delay_seconds=30.0,
                jitter_ratio=0.1,
            ),
            lease_seconds=60,
        ),
        object_store=object_store or FakeObjectStore(environment="local"),
        environment="local",
        clock=clock,
        job_store=store,
    )


def _drive(connector: JimengConnector, clock: FakeClock, *, worker_id: str = "w1", steps: int = 30) -> None:
    for _ in range(steps):
        record = connector.worker.process_once(worker_id=worker_id)
        clock.advance(timedelta(seconds=120))
        if record is not None and record.state in ("COMPLETED", "FAILED", "CANCELLED", "NEEDS_RECONCILE"):
            return


class TestInterface:
    def test_validate_config_reports_safe_defaults(self) -> None:
        report = _connector().validate_config()
        assert report.ok and report.mode == "mock" and report.enabled is False
        assert "cookie_auth=forbidden" in report.checks
        assert "webhook=disabled" in report.checks

    def test_dry_run_makes_no_transport_call(self) -> None:
        transport = JimengMockTransport(FIXTURES)
        connector = _connector(transport=transport)
        report = connector.dry_run(_request())
        assert report.ok and report.request_hash.startswith("sha256:")
        assert report.idempotency_key.startswith("run-0001_generate-media_")
        assert transport.create_calls == 0

    def test_real_mode_without_approval_is_blocked(self, tmp_path: Path) -> None:
        import yaml

        from test_config import REAL_ENV

        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        raw.update({"mode": "sandbox", "enabled": True})
        path = tmp_path / "jimeng.yaml"
        path.write_text(yaml.safe_dump(raw), encoding="utf-8")
        clock = _clock()
        with pytest.raises(RealModeBlockedError):
            JimengConnector(
                load_config(path),
                env=REAL_ENV,
                transport=JimengMockTransport(FIXTURES),
                queue=FakeQueueClient(
                    clock=clock,
                    retry_policy=RetryPolicy(
                        max_attempts=3,
                        base_delay_seconds=1.0,
                        max_delay_seconds=10.0,
                        jitter_ratio=0.1,
                    ),
                    lease_seconds=60,
                ),
                object_store=FakeObjectStore(environment="local"),
                environment="local",
                clock=clock,
            )

    def test_unsupported_output_format_is_typed(self) -> None:
        with pytest.raises(Exception):
            _request(output_format="mp4")  # schema rejects non-image formats

    def test_too_many_images_is_typed(self) -> None:
        connector = _connector(env={"JIMENG_MAX_IMAGES_PER_REQUEST": "1"})
        from jimeng_connector import RequestInvalidError

        with pytest.raises(RequestInvalidError):
            connector.execute(_request(image_count=2))


class TestHappyPathAndIdempotency:
    def test_create_persists_job_id_hash_and_idempotency_key(self) -> None:
        connector = _connector()
        record = connector.execute(_request())
        assert record.provider_job_id is not None
        assert record.request_hash.startswith("sha256:")
        assert record.idempotency_key == _request().idempotency_key()
        assert record.state == "CREATED"

    def test_poll_completes_downloads_validates_and_imports(self) -> None:
        clock = _clock()
        connector = _connector(clock=clock)
        connector.execute(_request())
        _drive(connector, clock)
        record = connector.get_status(_request().idempotency_key())
        assert record.state == "COMPLETED"
        assert record.asset_object_key is not None
        assert record.asset_object_key.startswith("local/tenant-cshi/content-agent-generated/run-0001/")
        assert record.asset_sha256 is not None

    def test_concurrent_submits_yield_one_provider_job(self) -> None:
        transport = JimengMockTransport(FIXTURES)
        connector = _connector(transport=transport)
        results: list[object] = []
        barrier = threading.Barrier(8)

        def _submit() -> None:
            barrier.wait()
            results.append(connector.execute(_request()))

        threads = [threading.Thread(target=_submit) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert len(results) == 8
        assert transport.create_calls == 1  # put_if_absent claim is atomic

    def test_100_duplicate_creates_yield_one_provider_job(self) -> None:
        transport = JimengMockTransport(FIXTURES)
        connector = _connector(transport=transport)
        records = [connector.execute(_request()) for _ in range(100)]
        job_ids = {r.provider_job_id for r in records}
        assert len(job_ids) == 1
        assert transport.create_calls <= 1  # store dedupes before transport

    def test_worker_restart_resume_with_shared_store_and_queue(self) -> None:
        clock = _clock()
        store = InMemoryJobStore()
        queue = FakeQueueClient(
            clock=clock,
            retry_policy=RetryPolicy(
                max_attempts=5, base_delay_seconds=1.0, max_delay_seconds=30.0, jitter_ratio=0.1
            ),
            lease_seconds=60,
        )
        transport = JimengMockTransport(FIXTURES)
        object_store = FakeObjectStore(environment="local")
        first = _connector(
            clock=clock, store=store, queue=queue, transport=transport, object_store=object_store
        )
        first.execute(_request())
        first.worker.process_once(worker_id="w1")  # one poll, still running
        clock.advance(timedelta(seconds=120))
        # 模拟 worker 重启：同一 store/queue/transport 的新实例继续处理。
        second = _connector(
            clock=clock, store=store, queue=queue, transport=transport, object_store=object_store
        )
        _drive(second, clock, worker_id="w2")
        record = second.get_status(_request().idempotency_key())
        assert record.state == "COMPLETED"

    def test_create_timeout_reconciles_by_idempotency_no_duplicate(self) -> None:
        transport = JimengMockTransport(FIXTURES, scenario="timeout_but_created")
        connector = _connector(transport=transport)
        record = connector.execute(_request())
        # timeout occurred but reconcile adopted the provider-side job
        assert record.state == "CREATED"
        assert record.provider_job_id is not None
        assert len(transport._jobs) == 1  # noqa: SLF001 - proves no duplicate


class TestFaultScenarios:
    def test_failed_job_is_typed_terminal_state(self) -> None:
        clock = _clock()
        connector = _connector("failed_job", clock=clock)
        connector.execute(_request())
        _drive(connector, clock)
        record = connector.get_status(_request().idempotency_key())
        assert record.state == "FAILED"
        assert record.error_code == "generation_failed"

    def test_cancel_marks_job_and_queue(self) -> None:
        connector = _connector()
        connector.execute(_request())
        record = connector.cancel(_request().idempotency_key())
        assert record.state == "CANCELLED"
        assert connector.worker.process_once(worker_id="w1") is None  # message cancelled

    def test_429_on_create_is_typed_rate_limited(self) -> None:
        connector = _connector("rate_limited_create")
        with pytest.raises(ProviderRateLimitedError):
            connector.execute(_request())
        record = connector.get_status(_request().idempotency_key())
        assert record.state == "NEEDS_RECONCILE"

    def test_url_expired_refetches_result_not_recreate(self) -> None:
        clock = _clock()
        transport = JimengMockTransport(FIXTURES, scenario="url_expired")
        connector = _connector(clock=clock, transport=transport)
        connector.execute(_request())
        _drive(connector, clock)
        record = connector.get_status(_request().idempotency_key())
        assert record.state == "COMPLETED"
        assert len(transport._jobs) == 1  # noqa: SLF001 - no second job

    def test_unknown_job_stops_and_goes_to_dlq(self) -> None:
        clock = _clock()
        transport = JimengMockTransport(FIXTURES)
        connector = _connector(clock=clock, transport=transport)
        connector.execute(_request())
        transport._scenario = "unknown_job"  # noqa: SLF001 - inject fault post-create
        create_calls_before = transport.create_calls
        for _ in range(10):
            connector.worker.process_once(worker_id="w1")
            clock.advance(timedelta(seconds=300))
        record = connector.get_status(_request().idempotency_key())
        assert record.state == "NEEDS_RECONCILE"
        assert record.error_code == "unknown_job"
        assert transport.create_calls == create_calls_before  # never re-created
        queue = connector.worker.queue
        assert isinstance(queue, FakeQueueClient)
        assert len(queue.dlq(POLL_TOPIC)) == 1  # human reconcile path


class TestSecurityValidation:
    def test_invalid_mime_rejected_and_nothing_stored(self) -> None:
        clock = _clock()
        object_store = FakeObjectStore(environment="local")
        connector = _connector("invalid_mime", clock=clock, object_store=object_store)
        connector.execute(_request())
        with pytest.raises(Exception, match="not an allowed image MIME"):
            for _ in range(10):
                connector.worker.process_once(worker_id="w1")
                clock.advance(timedelta(seconds=120))
        assert not object_store._objects  # noqa: SLF001 - nothing imported

    def test_malware_rejected_and_nothing_stored(self) -> None:
        clock = _clock()
        object_store = FakeObjectStore(environment="local")
        connector = _connector("malware", clock=clock, object_store=object_store)
        connector.execute(_request())
        with pytest.raises(Exception, match="malware"):
            for _ in range(10):
                connector.worker.process_once(worker_id="w1")
                clock.advance(timedelta(seconds=120))
        assert not object_store._objects  # noqa: SLF001

    def test_generated_and_approved_paths_are_separate_and_versioned(self) -> None:
        clock = _clock()
        object_store = FakeObjectStore(environment="local")
        connector = _connector(clock=clock, object_store=object_store)
        request = _request()
        connector.execute(request)
        _drive(connector, clock)
        record = connector.get_status(request.idempotency_key())
        assert record.asset_object_key is not None
        # promote to approved: separate path, own version
        from jimeng_connector.contracts import GeneratedAssetV1

        importer = connector.worker.importer
        generated = GeneratedAssetV1(
            request_id=request.request_id,
            provider_job_id=str(record.provider_job_id),
            object_key=record.asset_object_key,
            object_version=int(record.asset_object_version or 1),
            sha256=str(record.asset_sha256),
            provider_response_hash=str(record.asset_sha256),
            content_type="image/png",
            size_bytes=1,
        )
        approved = importer.promote_to_approved(request, generated)
        assert "content-agent-approved" in approved.object_key
        assert "content-agent-generated" in generated.object_key
        # a second promotion creates a NEW version, never in-place
        approved2 = importer.promote_to_approved(request, generated)
        assert approved2.object_version == approved.object_version + 1

    def test_object_versions_are_immutable(self) -> None:
        object_store = FakeObjectStore(environment="local")
        key = ObjectKey(
            environment="local", tenant="tenant-cshi", agent="content-agent-generated",
            run_id="run-0001", name="a.png",
        )
        object_store.put(key, b"v1", content_type="image/png")
        from infra_core.objectstore import OverwriteError

        with pytest.raises(OverwriteError):
            object_store.put(key, b"v1-modified", content_type="image/png", version=1)


class TestGovernance:
    def test_budget_stop_refuses_create(self) -> None:
        transport = JimengMockTransport(FIXTURES)
        connector = _connector(env={"JIMENG_PER_RUN_BUDGET": "0.001"}, transport=transport)
        with pytest.raises(BudgetExceededError):
            connector.execute(_request())
        assert transport.create_calls == 0

    def test_max_assets_per_run_cap(self) -> None:
        clock = _clock()
        connector = _connector(env={"JIMENG_MAX_ASSETS_PER_RUN": "1"}, clock=clock)
        connector.execute(_request())
        _drive(connector, clock)
        with pytest.raises(BudgetExceededError, match="max assets per run"):
            connector.execute(_request(node_id="generate-media-2"))

    def test_budget_alert_at_80_percent(self) -> None:
        connector = _connector()
        connector.budget.record_asset(connector.budget.per_run_budget * 0.85)
        assert any("per_run" in alert for alert in connector.budget.alerts)

    def test_budget_record_is_thread_safe(self) -> None:
        budget = MediaBudget(
            per_run_budget=100.0,
            daily_budget=100.0,
            max_assets_per_run=100_000,
        )

        def record_many() -> None:
            for _ in range(1000):
                budget.record_asset(0.001)

        threads = [threading.Thread(target=record_many) for _ in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert budget.run_assets == 20_000
        assert budget.run_spent == 20.0
        assert budget.daily_spent == 20.0

    def test_daily_budget_rolls_over_on_utc_date_change(self) -> None:
        clock = FakeClock(datetime(2026, 8, 28, 23, 59, tzinfo=timezone.utc))
        budget = MediaBudget(
            per_run_budget=10.0,
            daily_budget=1.0,
            max_assets_per_run=100,
            clock=clock,
        )
        budget.record_asset(0.9)
        with pytest.raises(BudgetExceededError, match="daily budget"):
            budget.check_before_create(0.2)

        clock.advance(timedelta(minutes=2))
        budget.check_before_create(0.2)
        budget.record_asset(0.2)
        assert budget.daily_spent == 0.2

    def test_job_rate_limiter_acquire_is_thread_safe(self) -> None:
        limiter = JobRateLimiter(
            clock=_clock(),
            requests_per_minute=5,
            max_concurrency=5,
            jobs_per_day=5,
        )
        acquired = 0
        rejected = 0
        result_lock = threading.Lock()

        def try_acquire() -> None:
            nonlocal acquired, rejected
            try:
                limiter.acquire_create()
            except LocalQueueFullError:
                with result_lock:
                    rejected += 1
            else:
                with result_lock:
                    acquired += 1

        threads = [threading.Thread(target=try_acquire) for _ in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert acquired == 5
        assert rejected == 15

    def test_jobs_per_day_limit(self) -> None:
        clock = _clock()
        connector = _connector(env={"JIMENG_JOBS_PER_DAY": "1"}, clock=clock)
        connector.execute(_request())
        with pytest.raises(LocalQueueFullError, match="jobs-per-day"):
            connector.execute(_request(node_id="generate-media-2"))


class TestReconcileAndNormalize:
    def test_reconcile_adopts_provider_job(self) -> None:
        transport = JimengMockTransport(FIXTURES)
        connector = _connector(transport=transport)
        request = _request()
        connector.execute(request)
        key = request.idempotency_key()
        record = connector.get_status(key)
        record.provider_job_id = None
        record.state = "NEEDS_RECONCILE"
        connector.worker.store.save(record)
        reconciled = connector.reconcile(key)
        assert reconciled.provider_job_id is not None
        assert reconciled.state == "CREATED"

    def test_get_status_unknown_key_typed(self) -> None:
        with pytest.raises(UnknownJobError):
            _connector().get_status("nope_nope_nope")

    def test_normalize_error_maps_to_connector_error_v1(self) -> None:
        connector = _connector()
        error = connector.normalize_error(
            ProviderRateLimitedError("rate limited"), trace_id="t-ne"
        )
        assert isinstance(error, ConnectorErrorV1)
        assert error.connector == "jimeng"
        assert error.code == "rate_limited"
        assert error.retryable is True

    def test_normalize_unknown_error(self) -> None:
        error = _connector().normalize_error(ValueError("boom"), trace_id="t-ue")
        assert error.code == "unexpected_error"
        assert error.retryable is False

    def test_normalize_error_sanitizes_credential_material(self) -> None:
        error = _connector().normalize_error(
            ValueError("api_key: sk-verysecret1234567890 leaked"), trace_id="t-sm"
        )
        assert "sk-verysecret1234567890" not in error.message
        assert "[redacted]" in error.message

