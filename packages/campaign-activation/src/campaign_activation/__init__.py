"""Campaign activation pipeline (Phase 03 / Subphase 05).

Idempotent operation ledger, atomic approval consumption, activation
worker with reconcile-before-retry and pending-approval compensation.
Real DEV/SIT reconciliation runs only in protected jobs.
"""

from campaign_activation.approvals import ApprovalConsumer, FakeApprovalConsumer
from campaign_activation.models import (
    ALLOWED_TRANSITIONS,
    ActivationError,
    ApprovalInvalidError,
    AuditWriteError,
    CompensationTask,
    DuplicateOperationError,
    IllegalTransitionError,
    OperationKey,
    OperationRecord,
    OperationStatus,
)
from campaign_activation.store import (
    AuditLog,
    CompensationQueue,
    FakeAuditLog,
    FakeCompensationQueue,
    FakeOperationStore,
    FakeOutbox,
    OperationStore,
    OutboxWriter,
    compensation_task_id,
)
from campaign_activation.worker import TOPIC, ActivationWorker, HandleResult

__all__ = [
    "ALLOWED_TRANSITIONS",
    "TOPIC",
    "ActivationError",
    "ActivationWorker",
    "ApprovalConsumer",
    "ApprovalInvalidError",
    "AuditLog",
    "AuditWriteError",
    "CompensationQueue",
    "CompensationTask",
    "DuplicateOperationError",
    "FakeApprovalConsumer",
    "FakeAuditLog",
    "FakeCompensationQueue",
    "FakeOperationStore",
    "FakeOutbox",
    "HandleResult",
    "IllegalTransitionError",
    "OperationKey",
    "OperationRecord",
    "OperationStatus",
    "OperationStore",
    "OutboxWriter",
    "compensation_task_id",
]
