"""Activation worker tests: one logical external write per key under retries,
crashes, duplicate delivery and unknown outcomes; audit/outbox fail closed;
partial success stops writes and only emits pending-approval compensation."""

from __future__ import annotations

from typing import Any, Mapping

import pytest

from connector_sdk.errors import ConnectorSdkError
from connector_sdk.models import ExternalWriteResult
from infra_core.queue import Message

from campaign_activation import AuditWriteError

from builders import CHANNEL, TENANT, ACCOUNT, TOKEN_REF, Harness, make_key, make_proposal

TOPIC = "campaign.activation"


def make_message(harness: Harness, *, delivery_id: int, attempt: int = 1) -> Message:
    proposal = make_proposal()
    return Message(
        topic=TOPIC,
        idempotency_key="idem-act-0001",
        payload={
            "tenant_id": TENANT,
            "channel": CHANNEL,
            "account_id": ACCOUNT,
            "approval_token_ref": TOKEN_REF,
            "input_hash": proposal.input_hash,
            "request": proposal.model_dump(mode="json"),
        },
        attempt=attempt,
        delivery_id=delivery_id,
    )


class TestHappyPath:
    def test_activation_creates_one_object_with_full_evidence(self) -> None:
        harness = Harness()
        harness.enqueue()
        result = harness.worker.run_once()
        assert result is not None and result.disposition == "ack"
        record = harness.store.get(make_key())
        assert record is not None
        assert record.status == "SUCCEEDED"
        assert record.external_object_id is not None
        assert record.approval_id == "appr-idem-act-0001"
        assert harness.connector.external_write_calls == 1
        # intent audit + outbox rows exist and precede the result rows
        kinds = [e["event"] for e in harness.audit.events]
        assert kinds.index("activation_intent") < kinds.index("activation_succeeded")
        assert any(e["event_type"] == "activation_intent" for e in harness.outbox.entries)
        intent = next(e for e in harness.audit.events if e["event"] == "activation_intent")
        assert intent["input_hash"] == record.input_hash
        assert intent["approval_id"] == record.approval_id

    def test_run_once_returns_none_on_empty_queue(self) -> None:
        harness = Harness()
        assert harness.worker.run_once() is None


class TestApprovalGates:
    def test_invalid_approval_means_zero_external_calls(self) -> None:
        harness = Harness()
        harness.enqueue(mint=False)  # token never minted
        result = harness.worker.run_once()
        assert result is not None and result.disposition == "ack"
        assert harness.connector.external_write_calls == 0
        record = harness.store.get(make_key())
        assert record is not None and record.status == "FAILED"
        assert any(e["event"] == "approval_rejected" for e in harness.audit.events)

    def test_token_reuse_across_keys_rejected(self) -> None:
        harness = Harness()
        harness.enqueue(idempotency_key="idem-act-0001")
        harness.enqueue(idempotency_key="idem-act-0002", mint=False)  # same token ref
        assert harness.worker.run_once() is not None
        assert harness.worker.run_once() is not None
        assert harness.connector.external_write_calls == 1
        second = harness.store.get(make_key("idem-act-0002"))
        assert second is not None and second.status == "FAILED"

    def test_retry_after_consume_does_not_need_second_token(self) -> None:
        # Crash between token consumption + intent and the external call:
        # the redelivery must proceed from the recorded intent, not re-consume.
        harness = Harness()
        proposal = harness.enqueue()
        harness.store.begin(
            key=make_key(),
            input_hash=proposal.input_hash,
            approval_id="appr-idem-act-0001",
            now="2026-09-14T00:00:00Z",
        )
        harness.approvals.consume(
            token_ref=TOKEN_REF,
            input_hash=proposal.input_hash,
            consumed_by="worker-0",
            now="2026-09-14T00:00:00Z",
        )
        result = harness.worker.run_once()
        assert result is not None and result.disposition == "ack"
        record = harness.store.get(make_key())
        assert record is not None and record.status == "SUCCEEDED"
        assert harness.connector.external_write_calls == 1


class TestDuplicateDelivery:
    def test_hundred_duplicate_deliveries_one_object(self) -> None:
        harness = Harness()
        harness.enqueue()
        assert harness.worker.run_once() is not None  # real processing
        ids = set()
        for delivery in range(2, 102):
            outcome = harness.worker.handle(make_message(harness, delivery_id=delivery))
            assert outcome.disposition == "ack"
            assert outcome.record is not None
            ids.add(outcome.record.external_object_id)
        assert len(ids) == 1
        assert harness.connector.external_write_calls == 1

    def test_replay_after_crash_before_ack_is_deduped(self) -> None:
        harness = Harness()
        harness.enqueue()
        message = harness.queue.receive(TOPIC, worker_id="worker-1")
        assert message is not None
        first = harness.worker.handle(message)
        assert first.disposition == "ack"
        # crash before ack: message stays leased/unacked; a replay of the same
        # payload must not call the provider again
        replay = harness.worker.handle(make_message(harness, delivery_id=999, attempt=2))
        assert replay.disposition == "ack"
        assert harness.connector.external_write_calls == 1
        assert any(e["event"] == "duplicate_delivery_deduped" for e in harness.audit.events)


class TestUnknownOutcome:
    def test_timeout_after_create_reconciles_before_retry(self) -> None:
        harness = Harness(fault="TIMEOUT_AFTER_EXTERNAL_CREATE")
        harness.enqueue()
        first = harness.worker.run_once()
        assert first is not None and first.disposition == "retry"
        record = harness.store.get(make_key())
        assert record is not None and record.status == "UNKNOWN"
        assert harness.connector.external_write_calls == 1

        second = harness.worker.run_once()  # redelivery: reconcile path
        assert second is not None and second.disposition == "ack"
        record = harness.store.get(make_key())
        assert record is not None and record.status == "RECONCILED"
        assert record.external_object_id is not None
        assert harness.connector.external_write_calls == 1  # never recreated
        assert any(e["event"] == "activation_reconciled" for e in harness.audit.events)

    def test_reconcile_required_error_parks_as_unknown_not_blind_retry(self) -> None:
        from connector_sdk.errors import ProviderTimeoutError

        class TimeoutOnceConnector:
            def __init__(self, inner: Any) -> None:
                self.inner = inner
                self.calls = 0

            def __getattr__(self, name: str) -> Any:
                return getattr(self.inner, name)

            def execute(self, request: Mapping[str, Any], **kwargs: Any) -> ExternalWriteResult:
                self.calls += 1
                if self.calls == 1:
                    raise ProviderTimeoutError("socket timeout; side effects unknown")
                return self.inner.execute(request, **kwargs)

        harness = Harness()
        wrapped = TimeoutOnceConnector(harness.connector)
        harness.worker.connectors = {CHANNEL: wrapped}
        harness.enqueue()
        first = harness.worker.run_once()
        assert first is not None and first.disposition == "retry"
        record = harness.store.get(make_key())
        # reconcile_required errors must park the record as UNKNOWN so the
        # next delivery reconciles first instead of retrying blindly.
        assert record is not None and record.status == "UNKNOWN"

        second = harness.worker.run_once()  # redelivery: reconcile path
        assert second is not None and second.disposition == "ack"
        record = harness.store.get(make_key())
        assert record is not None and record.status in {"SUCCEEDED", "RECONCILED"}
        assert harness.connector.external_write_calls == 1

    def test_confirmed_not_created_retries_same_key_once(self) -> None:
        class NotFoundThenCreateConnector:
            def __init__(self, inner: Any) -> None:
                self.inner = inner
                self.reconcile_calls = 0

            def __getattr__(self, name: str) -> Any:
                return getattr(self.inner, name)

            def reconcile(
                self, *, request: Mapping[str, Any], idempotency_key: str
            ) -> dict[str, Any]:
                self.reconcile_calls += 1
                return {
                    "outcome": "NOT_FOUND",
                    "external_object_id": None,
                    "idempotency_key": idempotency_key,
                }

        harness = Harness()
        wrapped = NotFoundThenCreateConnector(harness.connector)
        harness.worker.connectors = {CHANNEL: wrapped}

        proposal = harness.enqueue()
        harness.store.begin(
            key=make_key(),
            input_hash=proposal.input_hash,
            approval_id="appr-x",
            now="2026-09-14T00:00:00Z",
        )
        harness.store.transition(key=make_key(), to="UNKNOWN", now="2026-09-14T00:00:00Z")
        harness.approvals.consume(
            token_ref=TOKEN_REF,
            input_hash=proposal.input_hash,
            consumed_by="worker-0",
            now="2026-09-14T00:00:00Z",
        )
        result = harness.worker.run_once()
        assert result is not None and result.disposition == "ack"
        assert wrapped.reconcile_calls == 1
        record = harness.store.get(make_key())
        assert record is not None and record.status == "SUCCEEDED"
        assert harness.connector.external_write_calls == 1

    def test_still_unknown_goes_to_manual_queue_without_second_object(self) -> None:
        class AlwaysUnknownConnector:
            def __init__(self, inner: Any) -> None:
                self.inner = inner

            def __getattr__(self, name: str) -> Any:
                return getattr(self.inner, name)

            def reconcile(
                self, *, request: Mapping[str, Any], idempotency_key: str
            ) -> dict[str, Any]:
                raise ConnectorSdkError("reconcile query timed out")

        harness = Harness(fault="TIMEOUT_AFTER_EXTERNAL_CREATE")
        wrapped = AlwaysUnknownConnector(harness.connector)
        harness.worker.connectors = {CHANNEL: wrapped}
        harness.enqueue()

        outcomes = []
        for _ in range(3):  # queue max_attempts=3 -> DLQ afterwards
            result = harness.worker.run_once()
            assert result is not None
            outcomes.append(result.disposition)
        assert outcomes[0] == "retry"
        record = harness.store.get(make_key())
        assert record is not None and record.status == "WAITING_RECONCILIATION"
        assert harness.connector.external_write_calls == 1
        assert harness.queue.dlq(TOPIC), "exhausted message must land in the DLQ"


class TestPartialSuccess:
    def test_partial_success_stops_writes_and_creates_pending_task(self) -> None:
        class PartialError(ConnectorSdkError):
            code = "partial_mutate_success"
            retryable = False
            reconcile_required = True

            def __init__(self) -> None:
                super().__init__("partial hierarchy success")
                self.created_object_ids = ("ext-level-1",)

        class PartialConnector:
            def __init__(self, inner: Any) -> None:
                self.inner = inner

            def __getattr__(self, name: str) -> Any:
                return getattr(self.inner, name)

            def execute(self, request: Mapping[str, Any], **kwargs: Any) -> ExternalWriteResult:
                self.inner.external_write_calls += 1
                raise PartialError()

        harness = Harness()
        harness.worker.connectors = {CHANNEL: PartialConnector(harness.connector)}
        harness.enqueue()
        result = harness.worker.run_once()
        assert result is not None and result.disposition == "ack"
        record = harness.store.get(make_key())
        assert record is not None and record.status == "COMPENSATION_PENDING"

        assert len(harness.compensations.tasks) == 1
        task = harness.compensations.tasks[0]
        assert task.created_object_ids == ("ext-level-1",)
        assert task.status == "PENDING_APPROVAL"
        assert task.requires_approval is True
        assert harness.compensations.executed == 0  # L4: never auto-executed
        assert harness.connector.external_write_calls == 1


class TestFailClosed:
    def test_audit_failure_blocks_external_call(self) -> None:
        harness = Harness()
        harness.audit.fail = True
        harness.enqueue()
        result = harness.worker.run_once()
        assert result is not None and result.disposition == "retry"
        assert harness.connector.external_write_calls == 0

    def test_outbox_failure_blocks_external_call(self) -> None:
        harness = Harness()
        harness.outbox.fail = True
        harness.enqueue()
        result = harness.worker.run_once()
        assert result is not None and result.disposition == "retry"
        assert harness.connector.external_write_calls == 0

    def test_audit_failure_after_write_does_not_lose_result(self) -> None:
        # Result outbox/audit precede the SUCCEEDED transition: an audit
        # outage retries the delivery instead of losing the event, and the
        # replay is deduplicated by the connector ledger (no second write).
        harness = Harness()
        harness.audit.fail_after = 1  # intent event succeeds, next fails
        harness.enqueue()
        result = harness.worker.run_once()
        assert result is not None and result.disposition == "retry"
        assert harness.connector.external_write_calls == 1
        # audit backend recovers; the replayed delivery emits the events
        harness.audit.fail_after = None
        replay = harness.worker.handle(make_message(harness, delivery_id=998, attempt=2))
        assert replay.disposition == "ack"
        assert replay.record is not None
        assert replay.record.status == "SUCCEEDED"
        assert replay.record.external_object_id is not None
        assert harness.connector.external_write_calls == 1
        assert any(
            entry["event_type"] == "activation_succeeded"
            for entry in harness.outbox.entries
        )


class TestWorkerRestart:
    def test_new_worker_over_same_store_resumes_monotonically(self) -> None:
        from campaign_activation import ActivationWorker

        harness = Harness(fault="TIMEOUT_AFTER_EXTERNAL_CREATE")
        harness.enqueue()
        first = harness.worker.run_once()
        assert first is not None and first.disposition == "retry"

        restarted = ActivationWorker(
            queue=harness.queue,
            store=harness.store,
            approvals=harness.approvals,
            audit=harness.audit,
            outbox=harness.outbox,
            compensations=harness.compensations,
            connectors={CHANNEL: harness.connector},
            clock=harness.clock,
            worker_id="worker-2",
        )
        second = restarted.run_once()
        assert second is not None and second.disposition == "ack"
        record = harness.store.get(make_key())
        assert record is not None and record.status == "RECONCILED"
        assert harness.connector.external_write_calls == 1
