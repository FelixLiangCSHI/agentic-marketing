"""Connector contract tests: dry-run has zero external side effects, every
write needs approval + input hash + idempotency key, duplicate delivery and
retries never create a second object, quota exhaustion honors Retry-After,
timeout-after-create reconciles before retry, partial mutate stops writes,
and pagination interrupts resume from the last page token."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest

from infra_core.clock import FakeClock
from infra_core.secrets import FakeSecretResolver

from connector_sdk.errors import (
    AuthExpiredError,
    ProviderTimeoutError,
    RateLimitedError,
)

from google_ads_connector import (
    GoogleAdsConnector,
    MockGoogleAdsTransport,
    PartialMutateError,
)

from builders import make_config, make_policy, make_proposal

FAKE_NOW = datetime(2026, 9, 14, tzinfo=timezone.utc)
APPROVAL_REF = "config://approvals/campaign/run-p3-0004"
WINDOW = {"start": "2026-09-21", "end": "2026-09-27"}


def make_connector(fault: str | None = None) -> GoogleAdsConnector:
    return GoogleAdsConnector(
        config=make_config(),
        policy=make_policy(),
        secret_resolver=FakeSecretResolver(),
        clock=FakeClock(FAKE_NOW),
        transport=MockGoogleAdsTransport(fault=fault),
    )


def write_kwargs(proposal: Any, key: str = "idem-ga-0001") -> dict[str, Any]:
    return {
        "approval_token_ref": APPROVAL_REF,
        "input_hash": proposal.input_hash,
        "idempotency_key": key,
    }


class TestLifecycle:
    def test_validate_config_passes_in_mock(self) -> None:
        make_connector().validate_config()

    def test_health_check_reports_mock(self) -> None:
        health = make_connector().health_check()
        assert health["provider"] == "google_ads"
        assert health["mode"] == "mock"


class TestDryRun:
    def test_dry_run_has_no_external_side_effects(self) -> None:
        connector = make_connector()
        result = connector.dry_run(make_proposal().model_dump(mode="json"))
        assert result.valid is True
        assert connector.transport.write_calls == 0

    def test_dry_run_flags_violations(self) -> None:
        connector = make_connector()
        proposal = make_proposal(account_id="acct-unknown")
        result = connector.dry_run(proposal.model_dump(mode="json"))
        assert result.valid is False
        assert connector.transport.write_calls == 0


class TestWriteGates:
    def test_write_requires_approval_token(self) -> None:
        connector = make_connector()
        proposal = make_proposal()
        with pytest.raises(ValueError, match="approval"):
            connector.execute(
                proposal.model_dump(mode="json"),
                approval_token_ref="",
                input_hash=proposal.input_hash,
                idempotency_key="idem-ga-0001",
            )
        assert connector.transport.write_calls == 0

    def test_write_requires_sha256_input_hash(self) -> None:
        connector = make_connector()
        proposal = make_proposal()
        with pytest.raises(ValueError, match="input_hash"):
            connector.execute(
                proposal.model_dump(mode="json"),
                approval_token_ref=APPROVAL_REF,
                input_hash="not-a-hash",
                idempotency_key="idem-ga-0001",
            )
        assert connector.transport.write_calls == 0

    def test_write_requires_idempotency_key(self) -> None:
        connector = make_connector()
        proposal = make_proposal()
        with pytest.raises(ValueError, match="idempotency_key"):
            connector.execute(
                proposal.model_dump(mode="json"),
                approval_token_ref=APPROVAL_REF,
                input_hash=proposal.input_hash,
                idempotency_key="",
            )


class TestIdempotency:
    def test_create_then_duplicate_returns_same_object(self) -> None:
        connector = make_connector()
        proposal = make_proposal()
        first = connector.execute(proposal.model_dump(mode="json"), **write_kwargs(proposal))
        again = connector.execute(proposal.model_dump(mode="json"), **write_kwargs(proposal))
        assert first.outcome == "CREATED"
        assert again.outcome == "ALREADY_EXISTS"
        assert again.external_object_id == first.external_object_id
        assert connector.transport.write_calls == 1

    def test_hundred_duplicate_deliveries_create_one_object(self) -> None:
        connector = make_connector()
        proposal = make_proposal()
        document = proposal.model_dump(mode="json")
        ids = {
            connector.execute(document, **write_kwargs(proposal)).external_object_id
            for _ in range(100)
        }
        assert len(ids) == 1
        assert connector.transport.write_calls == 1

    def test_same_key_different_hash_rejected(self) -> None:
        connector = make_connector()
        proposal = make_proposal()
        connector.execute(proposal.model_dump(mode="json"), **write_kwargs(proposal))
        changed = make_proposal(total_limit=Decimal("2000.00"))
        with pytest.raises(ValueError, match="different input_hash"):
            connector.execute(changed.model_dump(mode="json"), **write_kwargs(changed))


class TestFaults:
    def test_quota_exhausted_maps_to_rate_limited_with_retry_after(self) -> None:
        connector = make_connector(fault="HTTP_429")
        proposal = make_proposal()
        with pytest.raises(RateLimitedError) as excinfo:
            connector.execute(proposal.model_dump(mode="json"), **write_kwargs(proposal))
        assert excinfo.value.retry_after_seconds == 23
        assert excinfo.value.retryable is True

    def test_auth_expired_propagates(self) -> None:
        connector = make_connector(fault="AUTH_EXPIRED")
        proposal = make_proposal()
        with pytest.raises(AuthExpiredError):
            connector.execute(proposal.model_dump(mode="json"), **write_kwargs(proposal))

    def test_timeout_after_create_yields_unknown_then_reconcile_finds_object(self) -> None:
        connector = make_connector(fault="TIMEOUT_AFTER_EXTERNAL_CREATE")
        proposal = make_proposal()
        document = proposal.model_dump(mode="json")
        result = connector.execute(document, **write_kwargs(proposal))
        assert result.outcome == "UNKNOWN"
        assert result.external_object_id is None

        reconciled = connector.reconcile(request=document, idempotency_key="idem-ga-0001")
        assert reconciled["outcome"] == "RECONCILED"
        assert reconciled["external_object_id"] is not None

        retry = connector.execute(document, **write_kwargs(proposal))
        assert retry.outcome == "ALREADY_EXISTS"
        assert retry.external_object_id == reconciled["external_object_id"]
        assert connector.transport.write_calls == 1

    def test_duplicate_delivery_fault_never_creates_second_object(self) -> None:
        connector = make_connector(fault="DUPLICATE_DELIVERY")
        proposal = make_proposal()
        result = connector.execute(proposal.model_dump(mode="json"), **write_kwargs(proposal))
        assert result.outcome == "ALREADY_EXISTS"
        assert connector.transport.write_calls == 0

    def test_partial_mutate_stops_writes_and_records_ids(self) -> None:
        connector = make_connector(fault="PARTIAL_MUTATE_SUCCESS")
        proposal = make_proposal()
        with pytest.raises(PartialMutateError) as excinfo:
            connector.execute(proposal.model_dump(mode="json"), **write_kwargs(proposal))
        assert excinfo.value.created_object_ids
        assert excinfo.value.reconcile_required is True

        document = connector.normalize_error(
            error=excinfo.value, trace_id="trace-0001", occurred_at="2026-09-14T00:00:00Z"
        )
        assert document["code"] == "partial_mutate_success"
        assert document["details"]["created_object_ids"] == list(
            excinfo.value.created_object_ids
        )


class TestReconcileAndStatus:
    def test_reconcile_unknown_key_is_not_found(self) -> None:
        connector = make_connector()
        result = connector.reconcile(request={}, idempotency_key="idem-missing")
        assert result["outcome"] == "NOT_FOUND"

    def test_get_status_binds_response_hash(self) -> None:
        connector = make_connector()
        proposal = make_proposal()
        created = connector.execute(proposal.model_dump(mode="json"), **write_kwargs(proposal))
        assert created.external_object_id is not None
        status = connector.get_status(
            external_object_id=created.external_object_id, idempotency_key="idem-ga-0001"
        )
        assert status["state"] == "PAUSED"
        assert status["source_response_hash"].startswith("sha256:")


class TestMetricsCollection:
    def test_collects_all_pages_with_raw_fields(self) -> None:
        connector = make_connector()
        rows = connector.collect_metrics(
            customer_id_ref="config://accounts/dev/google_ads/customer-id",
            external_object_id="customers/synthetic/campaigns/1",
            window=WINDOW,
        )
        fields = {row["provider_field_name"] for row in rows}
        assert "metrics.impressions" in fields
        assert "metrics.cost_micros" in fields
        assert all(row["source_response_hash"].startswith("sha256:") for row in rows)

    def test_page_interrupt_resumes_from_cursor_without_duplicates(self) -> None:
        connector = make_connector(fault="PAGE_INTERRUPT")
        with pytest.raises(ProviderTimeoutError):
            connector.collect_metrics(
                customer_id_ref="config://accounts/dev/google_ads/customer-id",
                external_object_id="customers/synthetic/campaigns/1",
                window=WINDOW,
            )
        resume_token = connector.last_page_token
        assert resume_token == "page-2"
        resumed = connector.collect_metrics(
            customer_id_ref="config://accounts/dev/google_ads/customer-id",
            external_object_id="customers/synthetic/campaigns/1",
            window=WINDOW,
            page_token=resume_token,
        )
        fields = [row["provider_field_name"] for row in resumed]
        assert "metrics.impressions" not in fields  # page 1 not re-read
        assert "metrics.cost_micros" in fields


class TestErrorNormalization:
    def test_no_secret_leaks_in_normalized_errors(self) -> None:
        connector = make_connector()
        error = AuthExpiredError(
            "grant rejected developer_token: synthetic-token-value"
        )
        document = connector.normalize_error(
            error=error, trace_id="trace-0002", occurred_at="2026-09-14T00:00:00Z"
        )
        assert "synthetic-token-value" not in str(document)
        assert "[redacted]" in str(document["message"])
        assert document["connector"] == "google_ads"
        assert document["code"] == "auth_expired"
