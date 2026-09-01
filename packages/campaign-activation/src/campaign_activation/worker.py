"""Activation worker: one logical external write per operation key.

Order of operations for a fresh activation:

1. atomically consume the single-use, hash-bound approval token — an
   invalid/reused token records ``FAILED`` and never reaches a connector;
2. write the operation intent plus audit and outbox rows — if either write
   fails the external call is not made (fail closed) and the delivery is
   retried;
3. call ``connector.execute`` with the approved input hash and the message
   idempotency key.

``UNKNOWN`` outcomes stop blind retries: the next delivery reconciles by
idempotency key first; a uniquely found object becomes ``RECONCILED``, a
confirmed-not-created outcome retries the same key, and an undecidable
outcome parks the operation in ``WAITING_RECONCILIATION`` until the queue
dead-letters the message for the manual queue. Partial hierarchy success
stops further writes, records every created external ID and emits a
pending-approval compensation task — L4 deletion/pausing is never executed
automatically. Replays and worker restarts are deduplicated through the
ledger, so duplicate deliveries can never create a second external object.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

from infra_core.clock import Clock
from infra_core.queue import Message, QueueClient

from connector_sdk.errors import ConnectorSdkError

from campaign_activation.approvals import ApprovalConsumer
from campaign_activation.models import (
    ApprovalInvalidError,
    AuditWriteError,
    CompensationTask,
    OperationKey,
    OperationRecord,
)
from campaign_activation.store import (
    AuditLog,
    CompensationQueue,
    OperationStore,
    OutboxWriter,
    compensation_task_id,
)

TOPIC = "campaign.activation"

_DEDUPE_STATUSES = frozenset(
    {"SUCCEEDED", "RECONCILED", "FAILED", "COMPENSATION_PENDING"}
)
_RECONCILE_STATUSES = frozenset({"UNKNOWN", "WAITING_RECONCILIATION"})


@dataclass(frozen=True)
class HandleResult:
    """Outcome of processing one delivery."""

    disposition: Literal["ack", "retry"]
    record: OperationRecord | None
    note: str


class ActivationWorker:
    """Queue consumer driving approvals, the ledger and one connector write."""

    def __init__(
        self,
        *,
        queue: QueueClient,
        store: OperationStore,
        approvals: ApprovalConsumer,
        audit: AuditLog,
        outbox: OutboxWriter,
        compensations: CompensationQueue,
        connectors: Mapping[str, Any],
        clock: Clock,
        worker_id: str,
    ) -> None:
        self.queue = queue
        self.store = store
        self.approvals = approvals
        self.audit = audit
        self.outbox = outbox
        self.compensations = compensations
        self.connectors = dict(connectors)
        self._clock = clock
        self.worker_id = worker_id

    # -- queue loop --------------------------------------------------------

    def run_once(self) -> HandleResult | None:
        """Receive and process at most one delivery."""
        message = self.queue.receive(TOPIC, worker_id=self.worker_id)
        if message is None:
            return None
        result = self.handle(message)
        if result.disposition == "ack":
            self.queue.ack(message)
        else:
            self.queue.nack(message, reason=result.note)
        return result

    # -- message processing --------------------------------------------------

    def handle(self, message: Message) -> HandleResult:
        """Process one delivery; pure with respect to the queue lease."""
        payload = message.payload
        key = OperationKey(
            tenant_id=str(payload["tenant_id"]),
            channel=str(payload["channel"]),
            account_id=str(payload["account_id"]),
            idempotency_key=message.idempotency_key,
        )
        input_hash = str(payload["input_hash"])
        request = dict(payload["request"])
        now = self._now()

        existing = self.store.get(key)
        if existing is not None and existing.status in _DEDUPE_STATUSES:
            self._audit_best_effort(
                {
                    "event": "duplicate_delivery_deduped",
                    "key": key.as_tuple(),
                    "status": existing.status,
                    "external_object_id": existing.external_object_id,
                    "occurred_at": now,
                }
            )
            return HandleResult("ack", existing, "duplicate delivery deduplicated")

        if existing is not None and existing.status in _RECONCILE_STATUSES:
            return self._reconcile_before_retry(
                key=key, request=request, token_ref=str(payload["approval_token_ref"])
            )

        if existing is None:
            # Fresh operation: the approval token must be consumed atomically
            # BEFORE any intent or external call.
            try:
                approval_id = self.approvals.consume(
                    token_ref=str(payload["approval_token_ref"]),
                    input_hash=input_hash,
                    consumed_by=self.worker_id,
                    now=now,
                )
            except ApprovalInvalidError as error:
                return self._reject_approval(
                    key=key, input_hash=input_hash, reason=str(error)
                )
        else:
            # INTENT survived a crash after consumption: never re-consume.
            approval_id = existing.approval_id

        record, _ = self.store.begin(
            key=key, input_hash=input_hash, approval_id=approval_id, now=now
        )

        # Operation intent + audit + outbox precede the external call and
        # fail closed: no rows, no write.
        try:
            self.audit.record(
                {
                    "event": "activation_intent",
                    "key": key.as_tuple(),
                    "input_hash": record.input_hash,
                    "approval_id": record.approval_id,
                    "occurred_at": now,
                }
            )
            self.outbox.append(
                aggregate_id=key.idempotency_key,
                event_type="activation_intent",
                payload={"key": list(key.as_tuple()), "input_hash": record.input_hash},
            )
        except AuditWriteError as error:
            return HandleResult("retry", record, f"fail closed before write: {error}")

        return self._execute(
            key=key,
            request=request,
            token_ref=str(payload["approval_token_ref"]),
            input_hash=input_hash,
        )

    # -- phases --------------------------------------------------------------

    def _execute(
        self,
        *,
        key: OperationKey,
        request: Mapping[str, Any],
        token_ref: str,
        input_hash: str,
    ) -> HandleResult:
        connector = self.connectors[key.channel]
        now = self._now()
        try:
            result = connector.execute(
                request,
                approval_token_ref=token_ref,
                input_hash=input_hash,
                idempotency_key=key.idempotency_key,
            )
        except ConnectorSdkError as error:
            created_ids = tuple(getattr(error, "created_object_ids", ()) or ())
            if created_ids:
                return self._partial_success(key=key, created_ids=created_ids, error=error)
            if error.reconcile_required:
                # Side effects unknown (timeout/5xx): never retry blindly;
                # park as UNKNOWN so the next delivery reconciles first.
                record = self.store.transition(key=key, to="UNKNOWN", now=now)
                self._audit_best_effort(
                    {
                        "event": "activation_unknown",
                        "key": key.as_tuple(),
                        "code": error.code,
                        "occurred_at": now,
                    }
                )
                return HandleResult(
                    "retry", record, "side effects unknown; reconcile before retry"
                )
            if error.retryable:
                return HandleResult(
                    "retry", self.store.get(key), f"retryable connector error: {error}"
                )
            return self._fail_verified(key=key, error=error)

        if result.outcome == "UNKNOWN":
            record = self.store.transition(
                key=key, to="UNKNOWN", now=now, operation_id=result.operation_id
            )
            self._audit_best_effort(
                {
                    "event": "activation_unknown",
                    "key": key.as_tuple(),
                    "operation_id": result.operation_id,
                    "occurred_at": now,
                }
            )
            return HandleResult("retry", record, "outcome unknown; reconcile before retry")

        # Outbox + audit are written BEFORE the terminal SUCCEEDED transition
        # so a storage failure retries the delivery instead of losing the
        # event forever; the connector ledger deduplicates the replayed
        # external write for the same idempotency key.
        try:
            self.outbox.append(
                aggregate_id=key.idempotency_key,
                event_type="activation_succeeded",
                payload={
                    "key": list(key.as_tuple()),
                    "external_object_id": result.external_object_id,
                    "outcome": result.outcome,
                },
            )
            self.audit.record(
                {
                    "event": "activation_succeeded",
                    "key": key.as_tuple(),
                    "external_object_id": result.external_object_id,
                    "outcome": result.outcome,
                    "occurred_at": now,
                }
            )
        except AuditWriteError as error:
            return HandleResult(
                "retry",
                self.store.get(key),
                f"fail closed before success record: {error}",
            )
        record = self.store.transition(
            key=key,
            to="SUCCEEDED",
            now=now,
            external_object_id=result.external_object_id,
            operation_id=result.operation_id,
        )
        return HandleResult("ack", record, "external write recorded")

    def _reconcile_before_retry(
        self, *, key: OperationKey, request: Mapping[str, Any], token_ref: str
    ) -> HandleResult:
        connector = self.connectors[key.channel]
        record = self.store.get(key)
        assert record is not None  # callers checked
        now = self._now()
        try:
            outcome = connector.reconcile(
                request=request, idempotency_key=key.idempotency_key
            )
        except Exception as error:  # undecidable: park, never recreate
            record = self.store.transition(key=key, to="WAITING_RECONCILIATION", now=now)
            self._audit_best_effort(
                {
                    "event": "reconcile_undecided",
                    "key": key.as_tuple(),
                    "reason": str(error),
                    "occurred_at": now,
                }
            )
            return HandleResult(
                "retry", record, "reconciliation undecided; manual queue via DLQ"
            )

        if outcome.get("outcome") == "RECONCILED":
            external_id = str(outcome["external_object_id"])
            try:
                self.outbox.append(
                    aggregate_id=key.idempotency_key,
                    event_type="activation_reconciled",
                    payload={"key": list(key.as_tuple()), "external_object_id": external_id},
                )
                self.audit.record(
                    {
                        "event": "activation_reconciled",
                        "key": key.as_tuple(),
                        "external_object_id": external_id,
                        "occurred_at": now,
                    }
                )
            except AuditWriteError as error:
                return HandleResult(
                    "retry", record, f"fail closed before reconcile record: {error}"
                )
            record = self.store.transition(
                key=key, to="RECONCILED", now=now, external_object_id=external_id
            )
            return HandleResult("ack", record, "unknown outcome reconciled to existing object")

        # Confirmed not created: retry the SAME idempotency key once per
        # delivery; the approval was already consumed for this key.
        self._audit_best_effort(
            {
                "event": "retry_after_confirmed_not_created",
                "key": key.as_tuple(),
                "occurred_at": now,
            }
        )
        return self._execute(
            key=key, request=request, token_ref=token_ref, input_hash=record.input_hash
        )

    def _partial_success(
        self, *, key: OperationKey, created_ids: tuple[str, ...], error: ConnectorSdkError
    ) -> HandleResult:
        now = self._now()
        record = self.store.transition(key=key, to="COMPENSATION_PENDING", now=now)
        task = CompensationTask(
            task_id=compensation_task_id(key),
            key=key,
            created_object_ids=created_ids,
            reason=str(error),
            created_at=now,
        )
        self.compensations.submit(task)
        self.outbox.append(
            aggregate_id=key.idempotency_key,
            event_type="compensation_pending",
            payload={
                "key": list(key.as_tuple()),
                "created_object_ids": list(created_ids),
                "task_id": task.task_id,
            },
        )
        self.audit.record(
            {
                "event": "compensation_pending",
                "key": key.as_tuple(),
                "created_object_ids": list(created_ids),
                "task_id": task.task_id,
                "occurred_at": now,
            }
        )
        return HandleResult("ack", record, "partial success; pending-approval compensation")

    def _fail_verified(self, *, key: OperationKey, error: ConnectorSdkError) -> HandleResult:
        now = self._now()
        record = self.store.get(key)
        if record is not None and record.status == "INTENT":
            record = self.store.transition(key=key, to="FAILED", now=now)
            disposition: Literal["ack", "retry"] = "ack"
        else:
            # From UNKNOWN the write may still exist; keep reconciling.
            disposition = "retry"
        self._audit_best_effort(
            {
                "event": "activation_failed",
                "key": key.as_tuple(),
                "code": error.code,
                "occurred_at": now,
            }
        )
        return HandleResult(disposition, record, f"non-retryable connector error: {error.code}")

    def _reject_approval(
        self, *, key: OperationKey, input_hash: str, reason: str
    ) -> HandleResult:
        now = self._now()
        try:
            record, _ = self.store.begin(
                key=key, input_hash=input_hash, approval_id="approval-rejected", now=now
            )
            record = self.store.transition(key=key, to="FAILED", now=now)
            self.audit.record(
                {
                    "event": "approval_rejected",
                    "key": key.as_tuple(),
                    "reason": reason,
                    "occurred_at": now,
                }
            )
        except AuditWriteError:
            return HandleResult("retry", self.store.get(key), "audit unavailable")
        return HandleResult("ack", record, f"approval rejected: {reason}")

    # -- helpers ---------------------------------------------------------------

    def _audit_best_effort(self, event: Mapping[str, Any]) -> None:
        """Read-only/duplicate bookkeeping never blocks a safe disposition."""
        try:
            self.audit.record(event)
        except AuditWriteError:
            pass

    def _now(self) -> str:
        return self._clock.now().strftime("%Y-%m-%dT%H:%M:%SZ")
